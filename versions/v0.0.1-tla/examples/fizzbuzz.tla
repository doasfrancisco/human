---- MODULE FizzBuzz ----

VARIABLES i, output

Init == i = 1 and output = ""

Step == i <= 15
    and output' = IF i % 15 = 0 THEN "FizzBuzz"
                  ELSE IF i % 3 = 0 THEN "Fizz"
                  ELSE IF i % 5 = 0 THEN "Buzz"
                  ELSE i
    and i' = i + 1

Next == Step

====
