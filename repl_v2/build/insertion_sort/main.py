def sort(items):
    result = list(items)
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result

if __name__ == "__main__":
    example = [5, 3, 8, 1, 9, 2, 7, 4, 6]
    sorted_list = sort(example)
    print("Original:", example)
    print("Sorted:  ", sorted_list)