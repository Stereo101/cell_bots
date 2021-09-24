# Cell Bots
## about
*Cell bots* are generically named cellular automata where cells are occupied by bots programed with
Zachtronics style assembly code most similar to [EXAPUNKS](https://www.zachtronics.com/exapunks/).
Bots can perform calculations, spawn more bots, move around, chuck messages through space,
and self assemble into structures to act as RAM or perform other tasks. *Cell bots* are an experimental form
of computation that offer an evolving visual component.

## messages
Instead of writing data to registers, bots can write data to a direction. Given a dimension like X,Y,Z aka D0,D1,D2 and polarity + or -,
a message will fly through space one space at a time in the direction they were fired until either its time to live hits 0 or it collides with another bot.
Bots may set their outgoing TTL with the 'ttl' instruction.

## message queue
Bots have a message queue, where messages they absorb are held until used. Q refers to the message queue, and can be read like a register.
When the message queue is empty and a bot attempts to read from Q, they will be stuck actively waiting on a message to arrive.
Bots may set the size of their own message queue, but the max size should be set small (4 or so) as to not allow avoidance of storage limitations.
If a queue size is set to 0, bots can only recieve messages if they are actively waiting on a read from Q.

## simulation design
Simulations can have any number of dimensions and give bots any number of registers.
These parameters can change what kind of approaches are possible for a given problem. 
The shorthand for a 2D simulation where bots have a single register would be *CB\_2\_1*.
Note that a bot designed for *CB\_a\_b* will embed and function in *CB\_x\_y* where
x>=a and y>=b. Simulation space should not be bounded.

## instruction listing
The type and number of instructions are not finalized. Some current instructions may later be cut,
and new instructions may still be added. 

## misc
Bots are currently use python3 integers, which are BigInts by default. Abusing this, bots can currently store as much data as they want
in a single register. This goes against the spirit of *Cell Bots*. This may be bounded to some fixed size int (either 8-bit or 64-bit) in the future.

Diagnal firing of messages in under consideration.

Using values held in registers to choose direction and polarity is under consideration.


