# skeleton

The detailed telling of a code file, written as the structure of the file itself: one line per part, plain words in the slots where code stands. It reads like the file, without the code. The user's free abstraction stays its own entry on top of it.

Validated on: hello_server/server.py.

## Rules

- Follow the structure of the file: one line per part, and what belongs to a part stands indented under it.
- Plain words fill the slots. Where the sketch leaves a slot open — "(explanation)" — fill it with what that part of the code does, in plain words.
- The pins are block pins: the name of a part pins to its block, and a filled slot pins to the block it tells.
- Keep every line as short as the sketch. The skeleton wins over the rail when the user thinks in the file's own structure.
- The abstraction above it keeps its own words verbatim and points down with `e<id>:` pins, so it inherits the lines through the chain.

## Example

```
import BaseHTTPRequestHandler, HTTPserver

class [Hello](Hello)
    ([answers every call](do_GET) with "hello world" as plain text)

[main](main)()
    serve on port 8000 "Hello" forever

if file is launched directly
    main()
```
