import numpy as np


class Reseau:
    def __init__(self, taille_entree, taille_cachee, taille_sortie):
        np.random.seed(42)
        # Initialisation He (essentielle pour ReLU)
        self.W1 = np.random.randn(taille_entree, taille_cachee) * np.sqrt(2.0 / taille_entree)
        self.b1 = np.zeros((1, taille_cachee))
        self.W2 = np.random.randn(taille_cachee, taille_sortie) * np.sqrt(2.0 / taille_cachee)
        self.b2 = np.zeros((1, taille_sortie))

    def forward(self, X):
        """Propagation avant."""
        self.Z1 = np.dot(X, self.W1) + self.b1
        self.A1 = np.maximum(0, self.Z1)
        self.Z2 = np.dot(self.A1, self.W2) + self.b2
        exp_scores = np.exp(self.Z2 - np.max(self.Z2, axis=1, keepdims=True))
        self.probas = exp_scores / np.sum(exp_scores, axis=1, keepdims=True)
        return self.probas

    def entrainer(self, X, y, epochs=1000, learning_rate=0.01):
        """Entrainement par descente de gradient."""
        for epoch in range(epochs):
            probas = self.forward(X)
            n = X.shape[0]
            erreur = -np.sum(y * np.log(probas + 1e-9)) / n

            dz2 = probas - y
            dW2 = np.dot(self.A1.T, dz2) / n
            db2 = np.sum(dz2, axis=0, keepdims=True) / n
            da1 = np.dot(dz2, self.W2.T)
            dz1 = da1 * (self.Z1 > 0)
            dW1 = np.dot(X.T, dz1) / n
            db1 = np.sum(dz1, axis=0, keepdims=True) / n

            self.W2 -= learning_rate * dW2
            self.b2 -= learning_rate * db2
            self.W1 -= learning_rate * dW1
            self.b1 -= learning_rate * db1

            pass  # progression gérée par terminal.py

    def sauvegarder(self, chemin):
        np.savez(chemin, W1=self.W1, b1=self.b1, W2=self.W2, b2=self.b2)

    def charger(self, chemin):
        data = np.load(chemin, allow_pickle=True)
        self.W1 = data["W1"]
        self.b1 = data["b1"]
        self.W2 = data["W2"]
        self.b2 = data["b2"]
