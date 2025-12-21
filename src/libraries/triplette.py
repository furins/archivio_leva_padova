import collections


class Triplette:
    lista = {}

    def __init__(self, filename):
        risultati = []
        with open(filename) as f:
            for name in f.readlines():
                name = name.strip()
                triplette = [name[x:x+3] for x in range(len(name)-2)]
                risultati.extend(triplette)
        c = collections.Counter(risultati)
        self.lista = dict(sorted(c.items(), key=lambda x: x[1], reverse=True))

    def save(self, filename):
        with open(filename, 'w') as f:
            for el in self.lista:
                f.write(f"{el},{self.lista[el]}\n")
