import collections
from typing import Dict, List, Optional, Set


class Triplette:
    lista = {}

    def __init__(self, filename):
        risultati: List[str] = []
        triplette_per_nome: List[Set[str]] = []
        with open(filename) as f:
            for name in f.readlines():
                name = name.strip()
                if not name:
                    continue
                triplette = [name[x:x+3] for x in range(len(name)-2)]
                risultati.extend(triplette)
                triplette_per_nome.append(set(triplette))
        c = collections.Counter(risultati)
        self.lista = dict(sorted(c.items(), key=lambda x: x[1], reverse=True))
        self._copertura = self._build_coverage(triplette_per_nome)

    def save(self, filename):
        with open(filename, 'w') as f:
            for el in self.lista:
                f.write(f"{el},{self.lista[el]}\n")

    def _build_coverage(self, triplette_per_nome: List[Set[str]]) -> Dict[str, Set[int]]:
        coverage: Dict[str, Set[int]] = {}
        for idx, triplette in enumerate(triplette_per_nome):
            for tripletta in triplette:
                coverage.setdefault(tripletta, set()).add(idx)
        return coverage

    def covering_triplette(
        self,
        target: str,
        available: Set[str],
    ) -> Optional[str]:
        if not available:
            return None
        target_set = self._copertura.get(target)
        if not target_set:
            return None
        best = None
        best_size = -1
        for candidate in available:
            if candidate == target:
                continue
            candidate_set = self._copertura.get(candidate)
            if not candidate_set:
                continue
            if target_set.issubset(candidate_set):
                candidate_size = len(candidate_set)
                if candidate_size > best_size:
                    best = candidate
                    best_size = candidate_size
        return best
