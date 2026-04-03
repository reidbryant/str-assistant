# STR Intake Skill

This skill defines how the orchestrator collects and validates the intake form for STR analysis.

## Required Inputs

The STR Assistant requires exactly three inputs before beginning analysis:

| Field | Description | Example |
|-------|-------------|---------|
| `zipcode` | 5-digit US ZIP code | `"90210"` |
| `min_price` | Minimum property purchase price (USD) | `200000` |
| `max_price` | Maximum property purchase price (USD) | `600000` |

## Collection Rules

1. If the user provides all three in their initial message, proceed immediately.
2. If any are missing, ask for them in a single follow-up message.
3. Validate: `min_price` must be less than `max_price`.
4. Validate: zipcode must be exactly 5 digits.
5. Never assume or fill in missing values.

## Intake Confirmation Message

Once all inputs are collected, confirm before proceeding:
```
Got it! I'll analyze STR opportunities in ZIP {zipcode} 
for properties priced between ${min_price:,} and ${max_price:,}.

Starting analysis now — this may take a minute...
```

## Passing Values to Subagents

Always pass prices as plain numbers (e.g., `"350000"`), not formatted strings.
