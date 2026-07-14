def insertion_sort(lst: list) -> None:
    for i in range(1, len(lst)):
        key = lst[i]
        j = i - 1
        while j >= 0 and lst[j] > key:
            lst[j + 1] = lst[j]
            j -= 1
        lst[j + 1] = key

if __name__ == "__main__":
    lst = [5, 3, 8, 1, 9, 2]
    insertion_sort(lst)
    print(lst)
