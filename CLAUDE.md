# Huntsman Payload - notes for Claude

Read [CONTEXT.md](CONTEXT.md) first (what this is, status, decisions), then [ROBOT.md](ROBOT.md) for the robot
this payload rides on. For anything about the robot newer than ROBOT.md, read the Huntsman project itself:
`C:\Users\craig\CLionProjects\Huntsman\CONTEXT.md` (or https://github.com/Virologyst/Project-Huntsman).

## Keep docs current

After a change to hardware, wiring, power, the robot link, decisions or status, update in the same change:
- `CONTEXT.md` - status checklist, decisions, open questions, next step, "Last updated" date
- `ROBOT.md` - only when the robot's interface or facts change (re-read Huntsman's CONTEXT.md first)
- If the payload changes something the robot side should know (new protocol, power draw, mounting), note it
  in Huntsman's `CONTEXT.md` too.

## Safety

- The robot's 55 kg servos can injure. Never send motion commands to `huntsman.local:23` (`stand`, `walk`,
  `turn`, `p`, `sweep`, joint moves...) to test code unless the user says the robot is clear or off.
  Read-only commands (`status`, `map`, `help`) are fine.
- Any byte sent to the robot console aborts the current move; the console takes one client at a time.

- Robot commands only go through the robot-link module (see CONTEXT.md decisions), with motion disabled by
  default and stop always allowed.
- The drill must stay disabled unless the user says an attachment is fitted; never trigger `/drill` or the
  auto-drill to test code.

## Target

Raspberry Pi 5, Raspberry Pi OS Bookworm, Python (Flask) backend + SvelteKit dashboard in `interface/`.
Code is developed on Windows and run on the Pi.

## Git

`origin` = https://github.com/Virologyst/Arachnid-Payload-System (the user's repo). Commit or push only when asked.
