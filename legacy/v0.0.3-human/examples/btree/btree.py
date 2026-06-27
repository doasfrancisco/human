"""Compiled from btree.human — DO NOT EDIT."""


class Node:
    def __init__(self, leaf=False):
        self.keys = []
        self.children = []
        self.leaf = leaf
        self.next = None  # leaf-level linked list


class BPlusTree:
    ORDER = 4  # branching factor

    def __init__(self):
        self.root = Node(leaf=True)

    def insert(self, product):
        key = product["price"]
        root = self.root

        if len(root.keys) == self.ORDER - 1:
            new_root = Node()
            new_root.children.append(self.root)
            self._split(new_root, 0)
            self.root = new_root

        self._insert_non_full(self.root, key, product)

    def _insert_non_full(self, node, key, product):
        i = len(node.keys) - 1

        if node.leaf:
            node.keys.append(None)
            while i >= 0 and key < node.keys[i]["price"]:
                node.keys[i + 1] = node.keys[i]
                i -= 1
            node.keys[i + 1] = product
        else:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            if len(node.children[i].keys) == self.ORDER - 1:
                self._split(node, i)
                if key > node.keys[i]:
                    i += 1
            self._insert_non_full(node.children[i], key, product)

    def _split(self, parent, index):
        child = parent.children[index]
        mid = (self.ORDER - 1) // 2
        new_node = Node(leaf=child.leaf)

        if child.leaf:
            new_node.keys = child.keys[mid:]
            child.keys = child.keys[:mid]
            new_node.next = child.next
            child.next = new_node
            push_up = new_node.keys[0]["price"]
        else:
            new_node.keys = child.keys[mid + 1:]
            push_up = child.keys[mid]
            child.keys = child.keys[:mid]
            new_node.children = child.children[mid + 1:]
            child.children = child.children[:mid + 1]

        parent.keys.insert(index, push_up)
        parent.children.insert(index + 1, new_node)

    def sorted(self):
        """Traverse leaf-level linked list — returns all products sorted by price."""
        node = self.root
        while not node.leaf:
            node = node.children[0]

        result = []
        while node:
            for item in node.keys:
                result.append(item)
            node = node.next
        return result


# -- Run --

tree = BPlusTree()

products = [
    {"name": "Keyboard", "price": 45.99},
    {"name": "Mouse", "price": 12.50},
    {"name": "Monitor", "price": 299.00},
    {"name": "USB Cable", "price": 5.99},
    {"name": "Headphones", "price": 89.00},
    {"name": "Webcam", "price": 55.00},
    {"name": "Mousepad", "price": 8.99},
    {"name": "Laptop Stand", "price": 34.50},
]

for p in products:
    tree.insert(p)

print("Products sorted by price (B+ tree traversal):\n")
for p in tree.sorted():
    print(f"  ${p['price']:>7.2f}  {p['name']}")
