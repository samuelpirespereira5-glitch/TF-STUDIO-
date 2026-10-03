# JARVIS — Community Social 2.0 + Game Studio 2.0

## Community / Discord-style
- New Community Center at `/comunidade`.
- New member-only room at `/comunidade/espacos/<space_id>/sala`.
- Text channels: geral, avisos, workshops.
- Voice/stage channel UI for lounge/workshop organization.
- Persistent member chat with polling refresh.
- Member list and event sidebar.
- Live event creation: chat, video and workshop.
- YouTube/Vimeo links are allowlisted and converted to privacy-friendly embed URLs; arbitrary iframe hosts are not accepted.
- Event attendance and live status.
- Private-space membership checks are enforced by the backend for channels/chat/events.
- New `/rankings` center with Global, Games, Community and Season views.
- Ranking is informational/gamification only and does not grant admin privileges.

## Game Studio 2.0
- Advanced game rules/settings: theme, camera, time limit, score goal, boss, music, checkpoints, difficulty scaling, save progress and story.
- Visual 32x16 level editor with block/item/enemy/power-up/goal/erase tools.
- Visual editor cells are converted into safe game entities by the server.
- Project JSON preview/export view inside the creator.
- Existing playable canvas preview, save/load and AI description-to-options flow preserved.
- User code is still never executed on the server.

## Validation
- Python syntax checks passed for modified Python files.
- JavaScript syntax checks passed for modified JS files.
- Game-spec smoke test passed.
- Existing project `final_expansion_check.py` still reports one pre-existing duplicate `/status` route between `app.py` and `routes_cyber.py`; this update did not introduce that duplicate.
