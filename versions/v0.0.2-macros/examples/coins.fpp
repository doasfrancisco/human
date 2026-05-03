macro change(denominations, target)
    variables
        remaining = {target}
        coins_used = 0

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

module CoinChange
    change([1, 5, 10, 25], 67)
