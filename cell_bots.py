import re

#Cell bot operations
#
#Bot limitations
#   some # of R/W registers that hold numbers
#   conditional flag
#   a TTL register that is only writable (default/max 255)
#   a FIFO QUEUE_MAX (default/max 255)
#
#INSTRUCTION LISTING
#   put src:R/I/Q dst:R/DIR
#   add src:R/I/Q dst:R/DIR
#   sub src:R/I/Q dst:R/DIR
#   mul src:R/I/Q dst:R/DIR
#   div src:R/I/Q result_dst:R/DIR mod_dst:R/DIR
#
#   tgt R/I/Q R/I/Q     test greater than
#   tlt R/I/Q R/I/Q     test less than
#   teq R/I/Q R/I/Q     test equal to
#
#   qmax R/I/DIR        set max queue size [0-255]
#   ttl R/I/DIR         set message ttl [0-255] where 0 means infinite TTL
#
#   jmp LABEL
#   jmpr R/I/Q
#   not R
#   id R
#   count BOT_NAME dst:R/DIR
#
#   spawn BOT_NAME DIR
#   fork DIR
#   kill DIR
#   move DIR
#   look DIR
#
#   die
#
#null is a valid register
#
#DIR should be of form AXIS(+/-)
#   ie X+ X- Y+ Y- Z+ Z-
#   allow for arbitrary number of dimensions
#   D0+ is the same as X+
#
#   
#   ?messages can move in multiple directions at once?
#
#spawning or forking another bot into an occupied space
#   will overwrite the previous bot 
#
#moving into an already occupied space will cause the move to fail
#moving sets the conditional register based on success
#
#writing to DIR will spawn a message moving in space
#messages move 1 space per tick in the direction they are fired
#when a message overlaps a bot, it is added to their message queue, the message is destroyed
#reading from an empty queue will cause the bot to hang until a message is recieved
#
#
#messages can pass through each other
#messages die when their TTL expires (or never do if TTL was set to 0)
#
#invalid instructions cause bot death (div 0,
#
#TURN PRIORITY
#messages are moved based on age (older = firster)
#bots code is ticked forward executed based on age (older = firster)
#bots killed before their turn don't execute anything

class Simulation:
    def __init__(self,dimensions,register_count):
        self.dimensions = dimensions
        self.register_count = register_count
        
        #indexs bots by location
        self.bot_grid = {}

        #set of live bots and their ids
        self.bot_id_set = set()
        self.messages = []

        self.recently_deceased = set()
        self.bot_code = {}
        self.bot_id_counts = {}

    def add_bot_code(self,bot_name,instruction_list):
        self.bot_code[bot_name] = instruction_list

    def register_bot(self,bot_obj):
        assert bot_obj.bot_name in self.bot_code
        if bot_obj.coords in self.bot_grid:
            #bot is overlapping another bot, kill it
            self.kill(self.bot_grid[bot_obj.coords])

        self.bot_grid[bot_obj.coords] = bot_obj
        self.bot_type_counts[bot_name] = self.bot_type_counts.get(bot_name,0) + 1
        self.bot_id_itr += 1
        return self.bot_id_itr

    def register_message(self,message):
        self.messages.append(message)
        pass 

    def kill(self,bot_obj):
        bot_obj.dead = True
        self.recently_deceased[bot_obj.id] = bot_obj
        self.bot_id_counts[bot_obj.bot_name] -= 1
        del self.bot_grid[bot_obj.coords]


    def tick(self):
        #MESSAGES, CHECK, MOVE, CHECK
        i = 0
        while i < len(self.messages):
            mesg = self.messages[i]
            
            #check for collision before moving
            #   (will happen if a bot moves into a message)
            if mesg.coords in self.bot_grid:
                self.bot_grid[mesg.coords].recv(mesg)
                self.messages.pop(i)
                continue
            #move and check for collision again
            #   (will happen if a message moves into a bot)
            mesg.tick()
            if mesg.coords in self.bot_grid:
                self.bot_grid[mesg.coords].recv(mesg)
                self.messages.pop(i)
                continue
            i += 1

        #TICK BOTS IN ORDER


        #cull dead bots
        for bot in self.bot_grid.values():
            if bot.dead:
                #TODO
                pass

        
class Message:
    def __init__(self,coords,velocity,value,simulation):
        self.coords = coords
        self.velocity = velocity
        assert len(coords) == len(velocity) 
        assert len(coords) == simulation.dimensions
        self.value = value
        self.id = simulation.register_message(self)

    def tick(self):
        self.coords = tuple(coords[i] + velocity[i] for i in range(coords)) 

class Cell_Bot:
    def __init__(self,bot_name,coords,simulation):
        assert bot_name in simulation.bot_code
        assert len(coords) == simulation.dimensions
        self.coords = coords
        self.instr_ptr = 0
        self.registers = [0]*simulation.register_count
        self.queue = []
        self.queue_size = 4
        self.ttl = 255
        
    def tick(self):
        instruction = simulation.bot_code[self.bot_name][instr_ptr]
        self.execute(instruction)

    def execute(self,instruction):
        pass
        
        
class Instruction_Set:
    instr_args = {
        "put":  [{"R","I","Q"},{"R","DIR"}],
        "add":  [{"R","I","Q"},{"R","DIR"}],
        "sub":  [{"R","I","Q"},{"R","DIR"}],
        "mul":  [{"R","I","Q"},{"R","DIR"}],
        "div":  [{"R","I","Q"},{"R","DIR"},{"R","DIR"}],

        "tgt":  [{"R","I","Q"},{"R","I","Q"}],
        "teq":  [{"R","I","Q"},{"R","I","Q"}],
        "tlt":  [{"R","I","Q"},{"R","I","Q"}],
        
        "qmax": [{"R","I","Q"}],
        "ttl":  [{"R","I","Q"}],
        "jmpr": [{"R","I","Q"}],

        "jmp":  [{"L"}],
        "not":  [{"R"}],
        "id":   [{"R","DIR"}],

        "count":[{"BOT"},{"R","DIR"}],
        "spawn":[{"BOT"},{"DIR"}],
        
        "fork": [{"DIR"}],
        "kill": [{"DIR"}],
        "die":  []
    }
  
    def __init__(self):
        self.label_index = None
        self.raw_code = None
        self.instructions = None

    def load(self,file_path):
        with open(file_path,"r") as code_fp:
            code = code_fp.readlines()
        self.compile(code)

    #simple parser, doesn't check for poor BOT names or LABEL names
    #   not all errors will be caught and explained
    def compile(self,code):
        final_instr_list = []
        tokenize_regex = r"\s+"

        #regex for matching different kinds of args
        register_regex = r"r\d+"
        d_style_dir_regex = r"D(?P<dim>\d)\s*(?P<dir>[\+\-])"
        x_style_dir_regex = r"(?P<dim>[XYZ])\s*(?P<dir>[\+\-])"
        register_regex = r"r(?P<reg_num>\d+)"
        immediate_regex = r"(?P<num>\d+)"

        label_offsets = {}
                
        line_number = -1
        code_line_number = -1
        for line in code:
            #always increment line_number
            line_number += 1

            symbol_offset = 0
            is_init_line = False
            is_cond_line = False
            cond_line_type = None

            line_symbols = re.split(tokenize_regex,line.strip())
            
            #skip empty lines
            if len(line_symbols) == 0 or line_symbols[0] == "":
                continue
            
            #skip comments
            if line_symbols[0].startswith("#"):
                continue
            #print(line_symbols)

            #check for a label
            if line_symbols[0].endswith(":"):
                label = line_symbols[0][:-1]
                if label in label_offsets:
                    print(f"Error on line {line_number}:")
                    print('"'," ".join(line_symbols),'"')
                    print(f"2nd definition of label '{label}'")
                    raise Exception("Compilation error")
                label_offsets[label] = line_number
                symbol_offset += 1
            
            #check if init token @ is present
            current_symbol = line_symbols[symbol_offset] 
            if current_symbol.startswith("@"): 
                is_init_line = True
                if len(current_symbol) > 1:
                    #strip @ token off this symbol
                    current_symbol = current_symbol[1:]
                else:
                    #go to the next symbol
                    symbol_offset += 1
                    current_symbol = line_symbols[symbol_offset]
             
            #check if + or - is present
            if current_symbol.startswith("+") or current_symbol.startswith("-"):
                is_cond_line = True
                cond_line_type = current_symbol.startswith("+")
                if len(current_symbol) > 1:
                    #strip +/- token off this symbol
                    current_symbol = current_symbol[1:]
                else:
                    #go to the next symbol
                    symbol_offset += 1
                    current_symbol = line_symbols[symbol_offset]
                


            #Ensure instruction type is valid
            instr_type = current_symbol
            if instr_type not in self.instr_args:
                print(f"Error on line {line_number}:")
                print('"'," ".join(line_symbols),'"')
                print(f"Unimplemented instruction '{instr_type}'")
                raise Exception("Compilation error")

            #verify arg count and ensure they match regex 
            expected_args = self.instr_args[instr_type]
            expected_arg_count = len(expected_args)

            arg_offset = 0
            args = []
            if expected_arg_count > len(line_symbols)-symbol_offset:
                print(f"Error on line {line_number}:")
                print('"'," ".join(line_symbols),'"')
                print(f"Instruction '{instr_type}' expects {expected_arg_count} arguments.")
                print(f"\tsyntax: {instr_type} {expected_args}")
                raise Exception("Compilation error")

            while arg_offset < expected_arg_count:
                #get next token
                symbol_offset += 1
                current_symbol = line_symbols[symbol_offset]
           
                #stop if we hit a comment 
                if current_symbol.startswith("#"):
                    break

                #ensure arg matches one of the expected inputs
                matched = False
                for arg_type in expected_args[arg_offset]:
                    if arg_type == "R":
                        m = re.match(register_regex,current_symbol)
                        if m:
                            args.append(["R",int(m.group("reg_num"))])
                            matched = True
                            break

                    elif arg_type == "I":
                        m = re.match(immediate_regex,current_symbol)
                        if m:
                            matched = True
                            args.append(["I",int(m.group("num"))])
                            break

                    elif arg_type == "Q":
                        if current_symbol == "Q":
                            matched = True
                            args.append(["Q"])
                            break

                    elif arg_type == "DIR":
                        m = re.match(d_style_dir_regex,current_symbol)
                        if m:
                            matched = True
                            args.append(["DIR",m.group("dim"),m.group("dir")])
                            break

                        #Normalize X,Y,Z style DIR into 0,1,2
                        m = re.match(x_style_dir_regex,current_symbol)
                        if m:
                            matched = True
                            x_dim = m.group("dim")
                            d = {"X":0,"Y":1,"Z":2}
                    
                            args.append(["DIR",m.group("dim"),m.group("dir")])
                            break
                    elif arg_type == "L":
                        #Labels are checked for validity at end of compile
                        matched = True
                        args.append(["LABEL",current_symbol])
                        break

                    elif arg_type == "BOT":
                        #BOT names are checked for validity at RUNTIME!!!
                        matched = True
                        args.append(["BOT",current_symbol])
                        break
                        
                if not matched:
                    print(f"Error on line {line_number}:")
                    print('"'," ".join(line_symbols),'"')
                    print(f"expected argument {arg_offset+1} to be of type {expected_args[arg_offset]}, but none matched.")
                    raise Exception("Compilation Error")

                arg_offset += 1
            if arg_offset < expected_arg_count:
                print(f"Error on line {line_number}:")
                print('"'," ".join(line_symbols),'"')
                print(f"Instruction '{instr_type}' expects {expected_arg_count} arguments, but only {arg_offset+1} were given")
                print(f"\tsyntax: {instr_type} {expected_args}")
                raise Exception("Compilation error")

            #ensure if there are remaining symbols, the next one starts with an '#' as to start a comment
            symbol_offset += 1
            if symbol_offset < len(line_symbols):
                if not line_symbols[symbol_offset].startswith("#"):
                    print(f"Error on line {line_number}:")
                    print('"'," ".join(line_symbols),'"')
                    print(f"Instruction '{instr_type}' expects {expected_arg_count} arguments, but more were given")
                    print(f"\tsyntax: {instr_type} {expected_args}")
                    raise Exception("Compilation error")
                    
            print(instr_type,args)
                
                
                
                

def test_bad_bots():
    bot_code_dir = "bad_bots"
    for bot in os.listdir(bot_code_dir):
        try:
            print("compiling",bot)
            bot_fp = os.path.join(bot_code_dir,bot)
            instr = Instruction_Set()
            instr.load(bot_fp)
        except Exception as e:
            print("error while compiling",bot,":",e)
        print()



def main():
    import os
    sim = Simulation(register_count=2,dimensions=2)
    bot_code_dir = "bots"
    for bot in os.listdir(bot_code_dir):
        try:
            print("compiling",bot)
            bot_fp = os.path.join(bot_code_dir,bot)
            instr = Instruction_Set()
            instr.load(bot_fp)
            print("success")
        except Exception as e:
            print("error while compiling",bot,":",e)
        print()

if __name__ == "__main__":
    main()
