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

# Greedy picks 4+1+1 = 3 coins. Optimal is 3+3 = 2 coins.
module CoinChange
    change([1, 3, 4], 6)
