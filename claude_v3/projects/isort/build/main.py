def insertion_sort(lst):
    for i in range(1, len(lst)):
        key = lst[i]
        j = i - 1
        while j >= 0 and lst[j] > key:
            lst[j + 1] = lst[j]
            j -= 1
        lst[j + 1] = key

if __name__ == "__main__":
    data = [32, 1, 32]
    insertion_sort(data)
    print(data)