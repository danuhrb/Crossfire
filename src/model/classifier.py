import os
import logging
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from config import MODEL_CHECKPOINT_DIR, CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)

FEATURE_DIM = 12


class DDoSFeatureDataset(Dataset):
    def __init__(self, features: np.ndarray, labels: np.ndarray = None):
        self.features = torch.FloatTensor(features)
        self.labels = torch.FloatTensor(labels) if labels is not None else None

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        if self.labels is not None:
            return self.features[idx], self.labels[idx]
        return self.features[idx]


class DDoSClassifier(nn.Module):
    """
    Input (12) -> FC(64) -> ReLU -> BN -> Dropout
    -> FC(32) -> ReLU -> BN -> Dropout
    -> FC(16) -> ReLU
    -> FC(1) -> Sigmoid
    """

    def __init__(self, input_dim: int = FEATURE_DIM, dropout: float = 0.3):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(dropout),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x).squeeze(-1)


class DDoSModelTrainer:
    def __init__(
        self,
        model: DDoSClassifier = None,
        lr: float = 1e-3,
        device: str = None,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = (model or DDoSClassifier()).to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.criterion = nn.BCELoss()
        self.best_val_loss = float("inf")

    def train_epoch(self, dataloader: DataLoader) -> float:
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        for features, labels in dataloader:
            features = features.to(self.device)
            labels = labels.to(self.device)

            self.optimizer.zero_grad()
            predictions = self.model(features)
            loss = self.criterion(predictions, labels)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        return total_loss / max(n_batches, 1)

    @torch.no_grad()
    def evaluate(self, dataloader: DataLoader) -> dict:
        self.model.eval()
        all_preds = []
        all_labels = []
        total_loss = 0.0
        n_batches = 0

        for features, labels in dataloader:
            features = features.to(self.device)
            labels = labels.to(self.device)

            predictions = self.model(features)
            loss = self.criterion(predictions, labels)
            total_loss += loss.item()
            n_batches += 1

            all_preds.extend(predictions.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

        preds = np.array(all_preds)
        labels = np.array(all_labels)
        binary_preds = (preds >= CONFIDENCE_THRESHOLD).astype(float)

        tp = ((binary_preds == 1) & (labels == 1)).sum()
        fp = ((binary_preds == 1) & (labels == 0)).sum()
        fn = ((binary_preds == 0) & (labels == 1)).sum()
        tn = ((binary_preds == 0) & (labels == 0)).sum()

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)

        return {
            "loss": total_loss / max(n_batches, 1),
            "accuracy": (tp + tn) / max(len(labels), 1),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    def fit(
        self,
        train_data: np.ndarray,
        train_labels: np.ndarray,
        val_data: np.ndarray = None,
        val_labels: np.ndarray = None,
        epochs: int = 50,
        batch_size: int = 64,
    ) -> list[dict]:
        train_dataset = DDoSFeatureDataset(train_data, train_labels)
        train_loader = DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True
        )

        val_loader = None
        if val_data is not None and val_labels is not None:
            val_dataset = DDoSFeatureDataset(val_data, val_labels)
            val_loader = DataLoader(val_dataset, batch_size=batch_size)

        history = []
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            record = {"epoch": epoch + 1, "train_loss": train_loss}

            if val_loader:
                val_metrics = self.evaluate(val_loader)
                record.update({f"val_{k}": v for k, v in val_metrics.items()})

                if val_metrics["loss"] < self.best_val_loss:
                    self.best_val_loss = val_metrics["loss"]
                    self.save_checkpoint("best_model.pt")

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} - "
                    f"train_loss: {train_loss:.4f}"
                    + (
                        f" - val_loss: {record.get('val_loss', 'N/A'):.4f}"
                        if val_loader
                        else ""
                    )
                )

            history.append(record)

        return history

    @torch.no_grad()
    def predict(self, features: np.ndarray) -> np.ndarray:
        self.model.eval()
        x = torch.FloatTensor(features).to(self.device)
        scores = self.model(x).cpu().numpy()
        return scores

    def classify(
        self, features: np.ndarray, threshold: float = None
    ) -> list[dict]:
        threshold = threshold or CONFIDENCE_THRESHOLD
        scores = self.predict(features)
        results = []
        for i, score in enumerate(scores):
            if score >= threshold:
                results.append({"index": i, "confidence": float(score)})
        return results

    def save_checkpoint(self, filename: str):
        os.makedirs(MODEL_CHECKPOINT_DIR, exist_ok=True)
        path = os.path.join(MODEL_CHECKPOINT_DIR, filename)
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "best_val_loss": self.best_val_loss,
                "timestamp": datetime.utcnow().isoformat(),
            },
            path,
        )
        logger.info(f"Checkpoint saved to {path}")

    def load_checkpoint(self, filename: str):
        path = os.path.join(MODEL_CHECKPOINT_DIR, filename)
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.best_val_loss = checkpoint.get("best_val_loss", float("inf"))
        logger.info(f"Loaded checkpoint from {path}")
