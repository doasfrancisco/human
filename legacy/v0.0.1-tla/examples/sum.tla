---- MODULE Sum ----

VARIABLES i, sum

Init == i = 1 and sum = 0

Add == i <= 3 and sum' = sum + i and i' = i + 1

Next == Add

SumInvariant == sum >= 0

Spec == Init and [][Next]_sum
====
