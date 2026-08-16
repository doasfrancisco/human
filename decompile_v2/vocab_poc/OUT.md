# vocab poc — compression through shared vocabulary

## dictionary

- **the retry dance** — It calls the given source read again and again, to a maximum number of tries, and after each failed try it waits, first for the given start wait and then for two times the last wait; it uses the data from the first try that is successful, or it raises a RuntimeError if all tries fail.
- **the leaf walk** — It goes down through all the levels of a value that is a number or a dictionary that contains more numbers and dictionaries, and it touches each value that is not a dictionary; such a value is a leaf.
- **the score list check** — It raises a ValueError if the input is not a list, if the list is empty, or if the list contains an item that is not a number.

## functions

### flaky_get

**original:** It takes the name of a source. If the failure count for that name is more than zero, it decreases the count by one and raises a ConnectionError with that name. If the count is zero, it returns the stored data for that name.

**rewritten:** It takes the name of a source. If the failure count for that name is more than zero, it decreases the count by one and raises a ConnectionError with that name. If the count is zero, it returns the stored data for that name.

### fetch_user

**original:** It takes no arguments. It calls the source read for the user a maximum of five times, and after each failed try it waits, first for 0.01 seconds and then for two times the last wait. It returns the user data from the first try that is successful, or it raises a RuntimeError if all five tries fail.

**rewritten:** It takes no arguments. It does the retry dance on the user source, with a maximum of five tries and a start wait of 0.01 seconds, and it returns the user data.

### fetch_orders

**original:** It takes no arguments. It calls the source read for the orders a maximum of four times, and after each failed try it waits, first for 0.02 seconds and then for two times the last wait. It returns the orders data from the first try that is successful, or it raises a RuntimeError if all four tries fail.

**rewritten:** It takes no arguments. It does the retry dance on the orders source, with a maximum of four tries and a start wait of 0.02 seconds, and it returns the orders data.

### fetch_prices

**original:** It takes no arguments. It calls the source read for the prices a maximum of six times, and after each failed try it waits, first for 0.01 seconds and then for two times the last wait. When a try is successful, it returns a new dictionary that keeps the same item codes but multiplies each price by 1.2 and rounds the result to two decimal places; if all six tries fail, it raises a RuntimeError.

**rewritten:** It takes no arguments. It does the retry dance on the prices source, with a maximum of six tries and a start wait of 0.01 seconds, and it returns a new dictionary that keeps the same item codes but multiplies each price by 1.2 and rounds the result to two decimal places.

### sum_leaves

**original:** It takes a value that is a number or a dictionary that contains more numbers and dictionaries. It goes down through all the levels of the dictionary and adds together each value that is not a dictionary. It returns that total.

**rewritten:** It takes a number or a dictionary. It does the leaf walk and adds all the leaves together. It returns that total.

### deep_flag

**original:** It takes a value that is a number or a dictionary that contains more numbers and dictionaries, and also a limit. It builds a new structure with the same keys and the same shape, but it replaces each value that is not a dictionary with True if the value is more than the limit, or with False if it is not. It returns that new structure.

**rewritten:** It takes a number or a dictionary, and also a limit. It does the leaf walk and builds a new structure with the same keys and the same shape, but each leaf becomes True if it is more than the limit, or False if it is not. It returns that new structure.

### average_scores

**original:** It takes a list of numbers. It raises a ValueError if the input is not a list, if the list is empty, or if the list contains an item that is not a number. If the input is correct, it returns the sum of the numbers divided by the count of the numbers.

**rewritten:** It takes a list of numbers. It does the score list check, then it returns the sum of the numbers divided by the count of the numbers.

### spread_scores

**original:** It takes a list of numbers. It raises a ValueError if the input is not a list, if the list is empty, or if the list contains an item that is not a number. If the input is correct, it returns the largest number minus the smallest number.

**rewritten:** It takes a list of numbers. It does the score list check, then it returns the largest number minus the smallest number.

### roman

**original:** It takes a positive whole number. It goes through the Roman values from 1000 down to 1, and for each value it adds the related glyph to the text and subtracts the value from the number, again and again while the number is not less than that value. It returns the text of the Roman numeral.

**rewritten:** It takes a positive whole number. It goes through the Roman values from 1000 down to 1, and for each value it adds the related glyph to the text and subtracts the value from the number, again and again while the number is not less than that value. It returns the text of the Roman numeral.

### luhn_ok

**original:** It takes a number or a text of digits. It reads the digits from right to left, and for each digit in an alternate position it multiplies the digit by two and subtracts nine if the result is more than nine, then it adds all the digits together. It returns True if the total divides by ten with no remainder, and False if it does not.

**rewritten:** It takes a number or a text of digits. It reads the digits from right to left, and for each digit in an alternate position it multiplies the digit by two and subtracts nine if the result is more than nine, then it adds all the digits together. It returns True if the total divides by ten with no remainder, and False if it does not.

## counts

- original explanations: 565 words
- rewritten explanations: 405 words
- dictionary: 133 words
- compressed total: 538 words
- ratio: 0.952
