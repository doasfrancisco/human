module WaterJugs

variables
    big = 0
    small = 0

action FillBig
    set big to 5

action FillSmall
    set small to 3

action EmptyBig
    set big to 0

action EmptySmall
    set small to 0

action PourSmallToBig
    set big to min(big + small, 5)
    set small to small - (min(big + small, 5) - big)

action PourBigToSmall
    set small to min(big + small, 3)
    set big to big - (min(big + small, 3) - small)

constraint
    big between 0 and 5
    small between 0 and 3

goal
    big = 4
