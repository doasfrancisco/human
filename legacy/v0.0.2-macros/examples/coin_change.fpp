module CoinChange

variables
    remaining = 67
    coins_used = 0

action Use25
    when remaining >= 25
    set remaining to remaining - 25
    set coins_used to coins_used + 1

action Use10
    when remaining >= 10
    set remaining to remaining - 10
    set coins_used to coins_used + 1

action Use5
    when remaining >= 5
    set remaining to remaining - 5
    set coins_used to coins_used + 1

action Use1
    when remaining >= 1
    set remaining to remaining - 1
    set coins_used to coins_used + 1

constraint
    remaining between 0 and 67
    coins_used between 0 and 67

goal
    remaining = 0
