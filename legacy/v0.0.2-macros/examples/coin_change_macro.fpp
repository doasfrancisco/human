# --- Macro definition ---
# This doesn't exist in fran++ yet. I'm designing what it WOULD look like.
#
# A macro takes parameters and expands into fran++ primitives.
# It runs at compile time — before the parser sees the result.

macro change(denominations, target)
    # 'denominations' is a list like [1, 5, 10, 25]
    # 'target' is a number like 67
    #
    # This macro GENERATES fran++ code. It's a program that writes a program.

    variables
        remaining = {target}
        coins_used = 0

    # Loop over denominations — this is the macro's power.
    # A template can't loop. A macro can.
    for coin in {denominations}
        action Use{coin}
            when remaining >= {coin}
            set remaining to remaining - {coin}
            set coins_used to coins_used + 1

    constraint
        remaining between 0 and {target}
        coins_used between 0 and {target}

    goal
        remaining = 0


# --- Usage ---
# The user writes ONE line. The macro expands it into the full spec.

module CoinChange
    change([1, 5, 10, 25], 67)


# --- What the compiler sees after macro expansion ---
# (the user never writes this — the macro generates it)
#
# module CoinChange
#
# variables
#     remaining = 67
#     coins_used = 0
#
# action Use1
#     when remaining >= 1
#     set remaining to remaining - 1
#     set coins_used to coins_used + 1
#
# action Use5
#     when remaining >= 5
#     set remaining to remaining - 5
#     set coins_used to coins_used + 1
#
# action Use10
#     when remaining >= 10
#     set remaining to remaining - 10
#     set coins_used to coins_used + 1
#
# action Use25
#     when remaining >= 25
#     set remaining to remaining - 25
#     set coins_used to coins_used + 1
#
# constraint
#     remaining between 0 and 67
#     coins_used between 0 and 67
#
# goal
#     remaining = 0
