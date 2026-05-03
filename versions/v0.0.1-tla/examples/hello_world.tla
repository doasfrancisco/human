---- MODULE HelloWorld ----

VARIABLE printed

Init == printed = FALSE

Print == printed = FALSE /\ printed' = TRUE

Next == Print

TypeInvariant == printed \in {TRUE, FALSE}

Spec == Init /\ [][Next]_printed
====
