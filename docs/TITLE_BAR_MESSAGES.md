# Title Bar Messages

Dashboard windows display contextual messages in the title bar when the system
needs to communicate tier restrictions, guidance, or warnings. Messages appear
inline below the window title and use color to indicate their category.

## When Messages Appear

**Tier restrictions**: When an operator selects a time range or feature that
is not available on their current plan, the title bar shows a message naming
the restriction and which tier removes it.

**System status**: When a view depends on data that is unavailable (e.g., no
chain data for the selected range, or an archive that has not been indexed yet),
the title bar shows guidance.

**Warnings**: When a view detects an anomaly (e.g., chain integrity issue, stale
data, or a configuration problem), the title bar shows a warning.

## Colors

| Color | Meaning | Examples |
|---|---|---|
| Amber | Tier information | "Personal includes a 10-day rolling history. 30-day is available on Crew and above." |
| Blue | Guidance | "Archives are not simulated in demo mode." |
| Red | Warning | Integrity issues, configuration errors |
| Green | Success | Confirmation of completed actions |

## Behavior

Messages persist for the duration of the condition that triggered them. If the
operator switches to a non-restricted range, the message disappears. Messages
do not stack; only the most recent relevant message is shown.

The function signature is `setTitleMessage(el, text, color, options)` where
`el` is the window container, `text` is the message content, `color` is one of
the values above, and `options` controls display behavior.
