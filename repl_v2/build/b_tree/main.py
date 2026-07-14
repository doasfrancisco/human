class BTree:
    class _Node:
        def __init__(self, leaf=True):
            self.keys = []
            self.children = []
            self.leaf = leaf

    def __init__(self):
        self.t = 3
        self.root = BTree._Node(leaf=True)

    def search(self, key):
        return self._search(self.root, key)

    def _search(self, node, key):
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            return True
        if node.leaf:
            return False
        return self._search(node.children[i], key)

    def insert(self, key):
        root = self.root
        if len(root.keys) == 2 * self.t - 1:
            new_root = BTree._Node(leaf=False)
            new_root.children.append(self.root)
            self._split_child(new_root, 0)
            self.root = new_root
        self._insert_non_full(self.root, key)

    def _insert_non_full(self, node, key):
        i = len(node.keys) - 1
        if node.leaf:
            node.keys.append(None)
            while i >= 0 and key < node.keys[i]:
                node.keys[i + 1] = node.keys[i]
                i -= 1
            node.keys[i + 1] = key
        else:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            if len(node.children[i].keys) == 2 * self.t - 1:
                self._split_child(node, i)
                if key > node.keys[i]:
                    i += 1
            self._insert_non_full(node.children[i], key)

    def _split_child(self, parent, i):
        t = self.t
        full = parent.children[i]
        new_node = BTree._Node(leaf=full.leaf)
        mid_key = full.keys[t - 1]
        new_node.keys = full.keys[t:]
        full.keys = full.keys[:t - 1]
        if not full.leaf:
            new_node.children = full.children[t:]
            full.children = full.children[:t]
        parent.keys.insert(i, mid_key)
        parent.children.insert(i + 1, new_node)

    def keys(self):
        result = []
        self._collect_keys(self.root, result)
        return result

    def _collect_keys(self, node, result):
        for i in range(len(node.keys)):
            if not node.leaf:
                self._collect_keys(node.children[i], result)
            result.append(node.keys[i])
        if not node.leaf:
            self._collect_keys(node.children[len(node.keys)], result)


if __name__ == "__main__":
    bt = BTree()
    for k in [10, 20, 5, 6, 12, 30, 7, 17, 3, 1, 15, 25, 35, 40, 50]:
        bt.insert(k)
    print(bt.keys())
    print(bt.search(15))
    print(bt.search(99))