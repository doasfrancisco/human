def area(w, h):
    return w * h


def total(rooms):
    out = 0
    for w, h in rooms:
        out += area(w, h)
    return out


if __name__ == "__main__":
    rooms = [(3, 4), (5, 2)]
    print(total(rooms))
