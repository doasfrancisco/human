def fizzbuzz(n):
    rules = {3: "Fizz", 5: "Buzz"}
    results = []
    for i in range(1, n + 1):
        output = ""
        for divisor, word in rules.items():
            if i % divisor == 0:
                output += word
        if output == "":
            output = str(i)
        results.append(output)
    return results

if __name__ == "__main__":
    for line in fizzbuzz(100):
        print(line)