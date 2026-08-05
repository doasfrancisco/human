from __future__ import annotations
from typing import Optional, Any


class BTreeNode:
    def __init__(self, t: int, leaf: bool = True):
        self.t = t
        self.leaf = leaf
        self.keys: list[Any] = []
        self.children: list[BTreeNode] = []

    def is_full(self) -> bool:
        return len(self.keys) == 2 * self.t - 1


class BTree:
    def __init__(self, t: int):
        self.t = t
        self.root: BTreeNode = BTreeNode(t, leaf=True)

    def search(self, key: Any, node: Optional[BTreeNode] = None) -> Optional[tuple[BTreeNode, int]]:
        if node is None:
            node = self.root
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            return (node, i)
        if node.leaf:
            return None
        return self.search(key, node.children[i])

    def insert(self, key: Any) -> None:
        root = self.root
        if root.is_full():
            new_root = BTreeNode(self.t, leaf=False)
            new_root.children.append(self.root)
            self._split_child(new_root, 0)
            self.root = new_root
        self._insert_non_full(self.root, key)

    def _insert_non_full(self, node: BTreeNode, key: Any) -> None:
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
            if node.children[i].is_full():
                self._split_child(node, i)
                if key > node.keys[i]:
                    i += 1
            self._insert_non_full(node.children[i], key)

    def _split_child(self, parent: BTreeNode, i: int) -> None:
        t = self.t
        full_child = parent.children[i]
        new_child = BTreeNode(t, leaf=full_child.leaf)
        mid = t - 1
        new_child.keys = full_child.keys[mid + 1:]
        if not full_child.leaf:
            new_child.children = full_child.children[t:]
            full_child.children = full_child.children[:t]
        parent.keys.insert(i, full_child.keys[mid])
        parent.children.insert(i + 1, new_child)
        full_child.keys = full_child.keys[:mid]

    def delete(self, key: Any) -> None:
        self._delete(self.root, key)
        if len(self.root.keys) == 0 and not self.root.leaf:
            self.root = self.root.children[0]

    def _delete(self, node: BTreeNode, key: Any) -> None:
        t = self.t
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            if node.leaf:
                node.keys.pop(i)
            else:
                if len(node.children[i].keys) >= t:
                    pred = self._get_predecessor(node.children[i])
                    node.keys[i] = pred
                    self._delete(node.children[i], pred)
                elif len(node.children[i + 1].keys) >= t:
                    succ = self._get_successor(node.children[i + 1])
                    node.keys[i] = succ
                    self._delete(node.children[i + 1], succ)
                else:
                    self._merge(node, i)
                    self._delete(node.children[i], key)
        else:
            if node.leaf:
                return
            if len(node.children[i].keys) < t:
                self._fill(node, i)
                i = 0
                while i < len(node.keys) and key > node.keys[i]:
                    i += 1
            self._delete(node.children[i], key)

    def _get_predecessor(self, node: BTreeNode) -> Any:
        while not node.leaf:
            node = node.children[-1]
        return node.keys[-1]

    def _get_successor(self, node: BTreeNode) -> Any:
        while not node.leaf:
            node = node.children[0]
        return node.keys[0]

    def _merge(self, parent: BTreeNode, i: int) -> None:
        t = self.t
        left = parent.children[i]
        right = parent.children[i + 1]
        left.keys.append(parent.keys.pop(i))
        left.keys.extend(right.keys)
        if not left.leaf:
            left.children.extend(right.children)
        parent.children.pop(i + 1)

    def _fill(self, parent: BTreeNode, i: int) -> None:
        t = self.t
        if i > 0 and len(parent.children[i - 1].keys) >= t:
            self._borrow_from_prev(parent, i)
        elif i < len(parent.children) - 1 and len(parent.children[i + 1].keys) >= t:
            self._borrow_from_next(parent, i)
        else:
            if i < len(parent.children) - 1:
                self._merge(parent, i)
            else:
                self._merge(parent, i - 1)

    def _borrow_from_prev(self, parent: BTreeNode, i: int) -> None:
        child = parent.children[i]
        sibling = parent.children[i - 1]
        child.keys.insert(0, parent.keys[i - 1])
        parent.keys[i - 1] = sibling.keys.pop()
        if not sibling.leaf:
            child.children.insert(0, sibling.children.pop())

    def _borrow_from_next(self, parent: BTreeNode, i: int) -> None:
        child = parent.children[i]
        sibling = parent.children[i + 1]
        child.keys.append(parent.keys[i])
        parent.keys[i] = sibling.keys.pop(0)
        if not sibling.leaf:
            child.children.append(sibling.children.pop(0))

    def traverse(self, node: Optional[BTreeNode] = None) -> list[Any]:
        if node is None:
            node = self.root
        result = []
        for i, key in enumerate(node.keys):
            if not node.leaf:
                result.extend(self.traverse(node.children[i]))
            result.append(key)
        if not node.leaf:
            result.extend(self.traverse(node.children[len(node.keys)]))
        return result


if __name__ == "__main__":
    tree = BTree(t=3)
    for key in [10, 20, 5, 6, 12, 30, 7, 17]:
        tree.insert(key)
    print(tree.traverse())
    print(tree.search(6))
    print(tree.search(15))
    tree.delete(6)
    print(tree.traverse())
    tree.delete(20)
    print(tree.traverse())