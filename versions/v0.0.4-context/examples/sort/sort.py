"""Compiled from .human via .context — DO NOT EDIT."""

def insertion_sort(arr):
    result = list(arr)
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result

if __name__ == "__main__":
    example = [1, 2, 3]
    print(insertion_sort(example))
