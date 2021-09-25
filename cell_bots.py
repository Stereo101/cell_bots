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

        self.bot_id_itr = 0

        self.recently_deceased = set()
        self.bot_code = {}
        self.bot_type_counts = {}

        self.time = 0

    def run(self):
        self.print_summary()
        while True:
            self.tick()
            self.print_summary()
            input()

    def print_summary(self):
            print(f"{self.time}: ...")
            print(self.bot_type_counts)
            for bot in self.bot_grid.values():
                print(f"{bot.bot_name} id:{bot.id} ip@{bot.instr_ptr}")
                print(bot.coords)
                print(bot.registers)
                print()


    def add_bot_code(self,bot_name,instruction_list):
        self.bot_code[bot_name] = instruction_list

    def register_bot(self,bot_obj):
        assert bot_obj.bot_name in self.bot_code
        if bot_obj.coords in self.bot_grid:
            #bot is overlapping another bot, kill it
            self.kill(self.bot_grid[bot_obj.coords])

        bot_obj.id = self.bot_id_itr
        self.bot_grid[bot_obj.coords] = bot_obj
        self.bot_type_counts[bot_obj.bot_name] = self.bot_type_counts.get(bot_obj.bot_name,0) + 1
        self.bot_id_itr += 1
        return self.bot_id_itr

    def register_message(self,message):
        self.messages.append(message)

    def kill(self,bot_obj):
        bot_obj.dead = True
        self.recently_deceased.add(bot_obj.id)
        self.bot_type_counts[bot_obj.bot_name] -= 1
        del self.bot_grid[bot_obj.coords]


    def tick(self):
        #check for message collision, move message, then check again
        i = 0
        while i < len(self.messages):
            mesg = self.messages[i]
            
            #check for collision before moving -> bot moved into a message
            if mesg.coords in self.bot_grid:
                self.bot_grid[mesg.coords].recv(mesg)
                self.messages.pop(i)
                continue
            #move and check again -> message moved into a bot
            mesg.tick()
            if mesg.coords in self.bot_grid:
                self.bot_grid[mesg.coords].recv(mesg)
                self.messages.pop(i)
                continue
            i += 1

        #Tick bots in order
        for bot in list(self.bot_grid.values()):
            if not bot.dead:
                bot.tick()

        self.time += 1

        
class Message:
    def __init__(self,coords,velocity,value,simulation,kill=False):
        self.coords = coords
        self.velocity = velocity
        assert len(coords) == len(velocity) 
        assert len(coords) == simulation.dimensions
        self.value = value
        self.id = simulation.register_message(self)
        self.kill = kill

    def tick(self):
        self.coords = tuple(coords[i] + velocity[i] for i in range(coords)) 

class Cell_Bot:
    def __init__(self,bot_name,coords,simulation):
        assert bot_name in simulation.bot_code
        assert len(coords) == simulation.dimensions

        self.bot_name = bot_name
        self.coords = coords
        self.simulation = simulation

        self.instr_ptr = 0
        self.registers = [0]*simulation.register_count
        self.queue = []
        self.queue_size = 4
        self.ttl = 255
        self.cond_state = False
        self.dead = False
        self.instruction_list = simulation.bot_code[self.bot_name].instructions
        self.label_index = simulation.bot_code[self.bot_name].label_index
        self.executed_inits = set()

        self.waiting_for_mesg = False
        self.arg_buffer = [0]*4

        #given by simulation when registered
        self.id = None
        
    def tick(self):
        if self.dead:
            return
        instruction = self.instruction_list[self.instr_ptr]
        self.execute(instruction)
    
    def die(self):
        self.dead = True
        self.simulation.kill(self)

    def f_die(self,args=None,srcs=None):
        assert len(args) == 0
        self.die()

    def f_add(self,args=None,srcs=None):
        assert len(args) == 2
        reg_index = args[1][1]
        self.registers[reg_index] += srcs[0]

    def f_sub(self,args=None,srcs=None):
        assert len(args) == 2
        reg_index = args[1][1]
        self.registers[reg_index] -= srcs[0]

    def f_mul(self,args=None,srcs=None):
        assert len(args) == 2
        reg_index = args[1][1]
        self.registers[reg_index] *= srcs[0]

    def f_div(self,args=None,srcs=None):
        assert len(args) == 3
        div_reg_index = args[1][1]
        remain_reg_index = args[1][2]
        self.registers[remain_reg_index] = self.registers[div_reg_index] % srcs[0]
        self.registers[div_reg_index] //= srcs[0]

    def f_put(self,args=None,srcs=None):
        assert len(args) == 2
        print(args)
        if args[1][0] == "DIR":
            print("shooting message",srcs[0],"".join(args[1][1:]))
        else:
            reg_index = args[1][1]
            self.registers[reg_index] = srcs[0]

    def f_jmp(self,args=None,srcs=None):
        assert len(args) == 1
        label = args[0][1]
        offset = self.label_index[label]
        self.instr_ptr = offset

    def f_jmpr(self,args=None,srcs=None):
        assert len(args) == 1
        pass

    def f_ttl(self,args=None,srcs=None):
        assert len(args) == 1
        pass

    def f_qmax(self,args=None,srcs=None):
        assert len(args) == 1
        pass

    def f_tlt(self,args=None,srcs=None):
        assert len(args) == 2
        self.cond_state = srcs[0] < srcs[1]

    def f_tgt(self,args=None,srcs=None):
        assert len(args) == 2
        self.cond_state = srcs[0] > srcs[1]

    def f_teq(self,args=None,srcs=None):
        assert len(args) == 2
        self.cond_state = srcs[0] == srcs[1]

    def f_not(self,args=None,srcs=None):
        assert len(args) == 1

    def parse_source(self,args):
        #If we are in the waiting state, check
        if self.waiting_for_mesg:
            if self.remaining_args != 0:
                #We can have enough args to execute the instr
                return True,[]
        else:
            #place items from queue into arg buffer
            print(args)
            q_args = sum(1 for a in args if a[0] == "Q")
            while q_args > 0 and len(self.queue) > 0:
                self.arg_buffer.append(self.queue.pop())
                q_args -= 1
            if q_args != 0:
                #Couldn't fill args from, Q, enter waiting state
                self.remaining_args = q_args
                self.waiting_for_mesg = True
                return True,[]
                
            
        ret = []
        print(args)
        print(list(args))
        for arg in args:
            source_type = arg[0]
            if source_type == "I":
                ret.append(arg[1])
            elif source_type == "R":
                ret.append(self.registers[arg[1]])
            elif source_type == "Q":
                ret.append(self.arg_buffer.pop(0))
            else:
                raise Exception("UNKNOWN SRC TYPE: " + source_type)
        return False,ret
            

    def recv(self,mesg):
        if mesg.kill:
            self.die()
        
        if self.waiting_for_mesg and self.remaining_args > 0:
            self.remaining_args -= 1
            self.arg_buffer.append(mesg.value)
            return True

        if len(self.queue) < self.queue_size:
            self.queue.insert(0,mesg.value)
            return True
        return False

    def execute(self,instruction):
        #dont inc pointer after jmp
        skip_inc_ip = "jmp" in instruction.instr_type
        print(instruction)

        #Check if we can actually fetch src's from Q 
        instr_arg_template = Instruction_Set.instr_args[instruction.instr_type] 
        print("arg_template",instr_arg_template)
        src_arg_indexs = [i for i in range(len(instr_arg_template)) if "src_" in instr_arg_template[i][0]]
        print("src_indexs",src_arg_indexs)
        src_args = [instruction.args[index] for index in src_arg_indexs]
        print("src_list",src_args)
        enter_wait,ret = self.parse_source(src_args)
        if enter_wait:
            return

        print("ret",ret)
        f = getattr(self,"f_" + instruction.instr_type) 
        f(args=instruction.args,srcs=ret)

        if instruction.is_init:
            self.executed_inits.add(self.instr_ptr)
        
        #finally increment instr ptr 
        if not skip_inc_ip:
            self.adv_ip()

        #find next valid instruction
        start = self.instr_ptr
        while True:
            next_instr = self.instruction_list[self.instr_ptr]
            if ((next_instr.is_init and self.instr_ptr in self.executed_inits) or (next_instr.is_cond and next_instr.cond_type != self.cond_state)):
                self.adv_ip()
                if self.instr_ptr == start:
                    self.die()
                    break
                continue
            break
    def adv_ip(self):
        self.instr_ptr += 1 
        if self.instr_ptr >= len(self.instruction_list):
            self.instr_ptr = 0

        
#struct to hold information about a single instruction

class Action: #lawsuit
    def __init__(self,instr_type, args, cond_type=None, is_init=False):
        self.instr_type = instr_type
        self.args = args
        self.cond_type = cond_type
        self.is_init = is_init
        self.is_cond = cond_type is not None

    def __repr__(self):
        if self.cond_type is not None and self.is_init:
            return f"@{'+' if self.cond_type else '-'}{self.instr_type} {self.args}"
        elif self.cond_type is not None:
            return f"{'+' if self.cond_type else '-'}{self.instr_type} {self.args}"
        elif self.is_init:
            return f"@{self.instr_type} {self.args}"
        else:
            return f"{self.instr_type} {self.args}"

class Instruction_Set:
    instr_args = {
        "put":  [   ("src_0",{"R","I","Q"}),
                    ("dst_0",{"R","DIR"})],

        "add":  [   ("src_0",{"R","I","Q"}),
                    ("dst_0",{"R","DIR"})],

        "sub":  [   ("src_0",{"R","I","Q"}),
                    ("dst_0",{"R","DIR"})],

        "mul":  [   ("src_0",{"R","I","Q"}),
                    ("dst_0",{"R","DIR"})],

        "div":  [   ("src_0",{"R","I","Q"}),
                    ("dst_0",{"R","DIR"}),
                    ("dst_1",{"R","DIR"})],

        "tgt":  [   ("src_0",{"R","I","Q"}),
                    ("src_1",{"R","I","Q"})],

        "teq":  [   ("src_0",{"R","I","Q"}),
                    ("src_1",{"R","I","Q"})],

        "tlt":  [   ("src_0",{"R","I","Q"}),
                    ("src_1",{"R","I","Q"})],
        
        "qmax": [   ("src_0",{"R","I","Q"})],
        "ttl":  [   ("src_0",{"R","I","Q"})],
        "jmpr": [   ("src_0",{"R","I","Q"})],

        "jmp":  [   ("src_0",{"L"})],
        "not":  [   ("dst_0",{"R"})],
        "id":   [   ("dst_0",{"R","DIR"})],

        "count":[   ("src_0",{"BOT"}),
                    ("dst_0",{"R","DIR"})],

        "spawn":[   ("src_0",{"BOT"}),
                    ("dst_0",{"DIR"})],
        
        "fork": [   ("src_0",{"DIR"})],
        "kill": [   ("src_0",{"DIR"})],
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
        self.raw_code = code
        instr_list = []
        tokenize_regex = r"\s+"

        #regex for matching different kinds of args
        register_regex = r"r\d+"
        d_style_dir_regex = r"D(?P<dim>\d)\s*(?P<dir>[\+\-])"
        x_style_dir_regex = r"(?P<dim>[XYZ])\s*(?P<dir>[\+\-])"
        register_regex = r"r(?P<reg_num>\d+)"
        immediate_regex = r"(?P<num>\d+)"

        label_offsets = {}
                
        line_number = -1
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
                    raise Exception("Compilation Error")
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
                raise Exception("Compilation Error")

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
                raise Exception("Compilation Error")

            while arg_offset < expected_arg_count:
                #get next token
                symbol_offset += 1
                current_symbol = line_symbols[symbol_offset]
           
                #stop if we hit a comment 
                if current_symbol.startswith("#"):
                    break

                #ensure arg matches one of the expected inputs
                matched = False
                
                for arg_type in expected_args[arg_offset][1]:
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
                raise Exception("Compilation Error")

            #ensure if there are remaining symbols, the ensure next one starts with an '#' as to start a comment
            symbol_offset += 1
            if symbol_offset < len(line_symbols):
                if not line_symbols[symbol_offset].startswith("#"):
                    print(f"Error on line {line_number}:")
                    print('"'," ".join(line_symbols),'"')
                    print(f"Instruction '{instr_type}' expects {expected_arg_count} arguments, but more were given")
                    print(f"\tsyntax: {instr_type} {expected_args}")
                    raise Exception("Compilation Error")
            act = Action(instr_type,args,cond_type=cond_line_type,is_init=is_init_line)
            instr_list.append([line_number,act]) 
            print(act)
    

        #mangle label index from raw line numbers to compiled line number
        for label in label_offsets.keys():
            index = label_offsets[label]
            #find first instruction >= label index
            instr_offset = 0
            while instr_offset < len(instr_list) and instr_list[instr_offset][0] < index:
                instr_offset += 1
            
            if instr_offset == len(instr_list):
                #set trailing labels to jump to start
                label_offsets[label] = 0
            else:
                label_offsets[label] = instr_offset

        #get rid of raw line numbers now that labels are adjusted
        instr_list = [x for _,x in instr_list]
        print(label_offsets)

        #check that labels actually exist
        for instr in instr_list:
            for arg_tup in instr.args:
                arg_type,arg,*_ = arg_tup
                if arg_type == "LABEL" and arg not in label_offsets: 
                    print(f"Error in instruction '{instr}'")
                    print(f"label '{arg}' was never defined")
                    raise Exception("Compilation Error")

        self.instructions = instr_list
        self.label_index = label_offsets
        return

def test_bad_bots():
    import os
    bot_code_dir = "bad_bots"
    for bot in os.listdir(bot_code_dir):
        try:
            print("compiling",bot)
            bot_fp = os.path.join(bot_code_dir,bot)
            instr = Instruction_Set()
            instr.load(bot_fp)
        except Exception as e:
            print("error while compiling",bot,":",e)
            if "Compilation Error" not in str(e):
                raise e
        print()



def main():
    import os
    sim = Simulation(register_count=2,dimensions=2)
    bot_code_dir = "bots"
    for bot in os.listdir(bot_code_dir):
        bot_name = bot.split(".")[0]
        try:
            print("compiling",bot)
            bot_fp = os.path.join(bot_code_dir,bot)
            instr = Instruction_Set()
            instr.load(bot_fp)
            print(f"compiled {bot} successfully.")
            sim.add_bot_code(bot_name,instr)
        except Exception as e:
            print("error while compiling",bot,":",e)
            if e != "Compilation Error":
                raise e
        print()
    main_bot = Cell_Bot("count_to_ten",(0,0),sim)
    #def __init__(self,bot_name,coords,simulation):
    sim.register_bot(main_bot)
    sim.run()

if __name__ == "__main__":
    main()
