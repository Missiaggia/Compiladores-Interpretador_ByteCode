import sys

class BytecodeInterpreter:
    def __init__(self):
        self.stack = []
        self.memory = {} # Simulates memory for variables 
        self.instructions = []
        self.ip = 0 # Instruction Pointer 
        self.labels = {}
        self.halted = False

    def _parse_arg(self, arg_str):
        """Helper to parse an argument to an int if possible, else returns it as a stripped string."""
        try:
            return int(arg_str)
        except ValueError:
            return arg_str.strip()

    def load_bytecode(self, bytecode_text):
        """
        Parses the bytecode text, resolves labels, and prepares instructions for execution.
        It performs two main passes:
        1. Identifies labels and their corresponding instruction indices, and collects raw instruction lines.
        2. Parses each instruction and its arguments, converting label names in jump/call targets to integer indices.
        """
        lines = bytecode_text.splitlines()
        
        raw_instructions_with_meta = [] 
        instruction_index_counter = 0 # Counts actual executable instructions for label mapping

        # Pass 1: Identify labels and collect potential instruction lines
        for line_num_human, line_content in enumerate(lines, 1):
            comment_start = line_content.find('#')
            if comment_start != -1:
                line = line_content[:comment_start].strip()
            else:
                line = line_content.strip()
            
            if not line: # Skip empty lines or lines that became empty 
                continue

            if line.endswith(':'): # It's a label 
                label_name = line[:-1].strip()
                if not label_name:
                    print(f"Error: Empty label name encountered at original line {line_num_human}.", file=sys.stderr)
                    self.halted = True
                    return
                if label_name in self.labels:
                    print(f"Error: Duplicate label '{label_name}' defined (original line {line_num_human}).", file=sys.stderr)
                    self.halted = True
                    return
                self.labels[label_name] = instruction_index_counter
            else:
                raw_instructions_with_meta.append({'text': line, 'original_line_num': line_num_human})
                instruction_index_counter += 1
        
        # Pass 2: Parse instructions and resolve label names to integer addresses
        for instr_data in raw_instructions_with_meta:
            line_text = instr_data['text']
            original_line_num = instr_data['original_line_num']
            
            parts = line_text.split()
            if not parts: 
                continue 
                
            opcode = parts[0].upper()
            args_str = parts[1:]
            parsed_args = []

            try:
                # Validate and parse arguments based on opcode
                if opcode in ['JMP', 'JZ', 'JNZ', 'CALL']: # These take one address argument 
                    if len(args_str) != 1:
                        raise ValueError(f"{opcode} expects 1 argument, got {len(args_str)}")
                    arg_val = self._parse_arg(args_str[0])
                    if isinstance(arg_val, str): # Label name
                        if arg_val not in self.labels:
                            raise ValueError(f"Undefined label '{arg_val}'")
                        parsed_args.append(self.labels[arg_val])
                    elif isinstance(arg_val, int): # Direct address
                        parsed_args.append(arg_val)
                    else:
                        raise ValueError(f"Invalid argument type for {opcode}: {arg_val}")
                elif opcode == 'PUSH': # PUSH takes an integer 
                    if len(args_str) != 1: raise ValueError("PUSH expects 1 integer argument")
                    parsed_args.append(int(args_str[0]))
                elif opcode in ['STORE', 'LOAD']: # STORE/LOAD take a variable name 
                    if len(args_str) != 1: raise ValueError(f"{opcode} expects 1 variable name argument")
                    var_name = self._parse_arg(args_str[0])
                    if not isinstance(var_name, str) or not var_name:
                         raise ValueError(f"{opcode} expects a non-empty string variable name.")
                    parsed_args.append(var_name)
                else: # For 0-argument opcodes or opcodes with other arg types (none in current spec)
                    if args_str: # Check if there are unexpected arguments
                         # Example: "ADD 5" would be an error as ADD takes no arguments from bytecode line
                         raise ValueError(f"{opcode} expects 0 arguments, got {len(args_str)}")
                    parsed_args = [] # No arguments to parse for these opcodes

            except ValueError as e:
                print(f"Error parsing instruction at original line {original_line_num} ('{line_text}'): {e}", file=sys.stderr)
                self.halted = True
                return
            
            self.instructions.append({'opcode': opcode, 'args': parsed_args, 'original_line_num': original_line_num})

    def run(self):
        """Executes the loaded bytecode instructions sequentially, updating the IP, stack, and memory."""
        if self.halted:
            return

        while self.ip < len(self.instructions) and not self.halted:
            instruction_data = self.instructions[self.ip]
            opcode = instruction_data['opcode']
            args = instruction_data['args']
            original_line_num = instruction_data['original_line_num']
            
            current_ip_for_reporting = self.ip # IP of the current instruction for error reporting
            next_ip_increment = 1 # Default: advance to the next instruction

            try:
                # Arithmetic and Stack Operations 
                if opcode == 'PUSH':
                    self.stack.append(args[0])
                elif opcode == 'POP':
                    if not self.stack: raise IndexError("POP from empty stack")
                    self.stack.pop()
                elif opcode in ['ADD', 'SUB', 'MUL', 'DIV', 'MOD']:
                    if len(self.stack) < 2: raise IndexError(f"{opcode} requires two values on the stack")
                    op2 = self.stack.pop()
                    op1 = self.stack.pop()
                    if opcode == 'ADD': self.stack.append(op1 + op2)
                    elif opcode == 'SUB': self.stack.append(op1 - op2)
                    elif opcode == 'MUL': self.stack.append(op1 * op2)
                    elif opcode == 'DIV':
                        if op2 == 0: raise ZeroDivisionError("Division by zero")
                        self.stack.append(op1 // op2) # Integer division
                    elif opcode == 'MOD':
                        if op2 == 0: raise ZeroDivisionError("Modulo by zero")
                        self.stack.append(op1 % op2)
                elif opcode == 'NEG':
                    if not self.stack: raise IndexError("NEG from empty stack")
                    self.stack.append(-self.stack.pop())
                
                # Variable Operations 
                elif opcode == 'STORE':
                    if not self.stack: raise IndexError("STORE from empty stack")
                    var_name = args[0]
                    self.memory[var_name] = self.stack.pop() # STORE pops the value 
                elif opcode == 'LOAD':
                    var_name = args[0]
                    if var_name not in self.memory: raise KeyError(f"Variable '{var_name}' not initialized")
                    self.stack.append(self.memory[var_name]) # LOAD pushes the value 

                # Control Flow Operations 
                elif opcode == 'JMP':
                    target_ip = args[0]
                    if not (0 <= target_ip <= len(self.instructions)):
                        raise ValueError(f"JMP to invalid address: {target_ip}")
                    self.ip = target_ip
                    next_ip_increment = 0 
                elif opcode == 'JZ' or opcode == 'JNZ':
                    if not self.stack: raise IndexError(f"{opcode} from empty stack")
                    val = self.stack.pop()
                    condition_met = (opcode == 'JZ' and val == 0) or \
                                    (opcode == 'JNZ' and val != 0)
                    if condition_met:
                        target_ip = args[0]
                        if not (0 <= target_ip <= len(self.instructions)):
                             raise ValueError(f"{opcode} to invalid address: {target_ip}")
                        self.ip = target_ip
                        next_ip_increment = 0
                elif opcode == 'HALT':
                    self.halted = True # Stop execution
                
                # Comparison Operations 
                elif opcode in ['EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE']:
                    if len(self.stack) < 2: raise IndexError(f"{opcode} requires two values on the stack")
                    op2 = self.stack.pop()
                    op1 = self.stack.pop()
                    result = 0
                    if   opcode == 'EQ':  result = 1 if op1 == op2 else 0
                    elif opcode == 'NEQ': result = 1 if op1 != op2 else 0
                    elif opcode == 'LT':  result = 1 if op1 < op2  else 0
                    elif opcode == 'GT':  result = 1 if op1 > op2  else 0
                    elif opcode == 'LE':  result = 1 if op1 <= op2 else 0
                    elif opcode == 'GE':  result = 1 if op1 >= op2 else 0
                    self.stack.append(result)

                # Functions and I/O Operations 
                elif opcode == 'CALL':
                    target_ip = args[0]
                    if not (0 <= target_ip < len(self.instructions)): 
                        raise ValueError(f"CALL to invalid address: {target_ip}")
                    self.stack.append(current_ip_for_reporting + 1) # Push return address (instr after CALL) 
                    self.ip = target_ip
                    next_ip_increment = 0
                elif opcode == 'RET':
                    if not self.stack: raise IndexError("RET from empty stack (no return address)")
                    ret_addr = self.stack.pop() # RET pops the return address 
                    if not isinstance(ret_addr, int) or not (0 <= ret_addr <= len(self.instructions)):
                        raise ValueError(f"Invalid return address on stack: {ret_addr}")
                    self.ip = ret_addr
                    next_ip_increment = 0
                
                elif opcode == 'PRINT': # Works with standard output 
                    if not self.stack: raise IndexError("PRINT from empty stack")
                    # PRINT peeks at the top of the stack but does not pop it.
                    # This is inferred from  (stack content shown after PRINT)
                    # and  (example function uses PRINT then POP).
                    print(self.stack[-1]) 
                elif opcode == 'READ': # Works with standard input 
                    try:
                        val_str = input() 
                        val_int = int(val_str) # Expects an integer input
                        self.stack.append(val_int)
                    except ValueError:
                        raise ValueError(f"READ expects an integer input, received: '{val_str}'")
                    except EOFError:
                        print(f"Runtime Error at original line {original_line_num}: {opcode} - EOFError: No input for READ.", file=sys.stderr)
                        self.halted = True
                
                else: # Handles unknown opcodes
                    # LABELs and empty instructions are filtered out during load_bytecode 
                    raise ValueError(f"Unknown or unimplemented opcode: {opcode}")

                if not self.halted and next_ip_increment > 0:
                    self.ip += next_ip_increment # Move to next instruction if IP wasn't set by jump/call/ret
            
            except (IndexError, ValueError, KeyError, ZeroDivisionError) as e:
                print(f"Runtime Error at instruction index {current_ip_for_reporting} (original line {original_line_num}): {opcode} {' '.join(map(str,args))} - {type(e).__name__}: {e}", file=sys.stderr)
                self.halted = True
        
if __name__ == '__main__':
    # Read the entire bytecode from standard input 
    bytecode_input_text = sys.stdin.read()
    
    interpreter = BytecodeInterpreter()
    interpreter.load_bytecode(bytecode_input_text) 
    
    if not interpreter.halted: # Proceed to run only if loading was successful
        interpreter.run()