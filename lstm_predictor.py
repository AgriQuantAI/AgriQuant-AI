"""
AgriQuant AI - LSTM Deep Learning Price Predictor
Neural network approach for time-series ag commodity futures prediction
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. LSTM predictor will run in compatibility mode.")


class TimeSeriesDataset(Dataset):
    """PyTorch Dataset for time series data"""
    
    def __init__(self, sequences: np.ndarray, targets: np.ndarray):
        self.sequences = torch.FloatTensor(sequences)
        self.targets = torch.FloatTensor(targets)
    
    def __len__(self):
        return len(self.sequences)
    
    def __getitem__(self, idx):
        return self.sequences[idx], self.targets[idx]


class LSTMPricePredictor(nn.Module):
    """
    Multi-layer LSTM network for ag commodity futures price prediction
    Captures temporal dependencies in weather and market patterns
    """
    
    def __init__(
        self,
        input_size: int = 50,
        hidden_size: int = 128,
        num_layers: int = 3,
        dropout: float = 0.2,
        bidirectional: bool = True
    ):
        super(LSTMPricePredictor, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
            bidirectional=bidirectional
        )
        
        # Attention mechanism
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size * (2 if bidirectional else 1),
            num_heads=8,
            dropout=dropout,
            batch_first=True
        )
        
        # Fully connected layers
        fc_input_size = hidden_size * (2 if bidirectional else 1)
        self.fc1 = nn.Linear(fc_input_size, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 1)
        
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.batch_norm1 = nn.BatchNorm1d(64)
        self.batch_norm2 = nn.BatchNorm1d(32)
        
    def forward(self, x):
        # LSTM forward pass
        lstm_out, (hidden, cell) = self.lstm(x)
        
        # Apply attention
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        
        # Take the output from the last time step
        last_output = attn_out[:, -1, :]
        
        # Fully connected layers with batch norm and dropout
        out = self.fc1(last_output)
        out = self.batch_norm1(out)
        out = self.relu(out)
        out = self.dropout(out)
        
        out = self.fc2(out)
        out = self.batch_norm2(out)
        out = self.relu(out)
        out = self.dropout(out)
        
        out = self.fc3(out)
        
        return out


class DeepLearningPredictor:
    """
    Deep learning-based price prediction system
    Uses LSTM with attention for sophisticated pattern recognition
    """
    
    def __init__(
        self,
        sequence_length: int = 30,
        input_features: int = 50,
        model_path: str = "models/lstm_predictor.pth"
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available. Install with: pip install torch")
        
        self.sequence_length = sequence_length
        self.input_features = input_features
        self.model_path = model_path
        
        # Initialize model
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = LSTMPricePredictor(input_size=input_features).to(self.device)
        
        # Training components
        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001, weight_decay=1e-5)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', patience=5, factor=0.5
        )
        
        # Normalization parameters
        self.feature_mean = None
        self.feature_std = None
        self.target_mean = None
        self.target_std = None
    
    def prepare_sequences(
        self,
        data: pd.DataFrame,
        target_column: str = 'price_change_7d'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert time series data into sequences for LSTM
        
        Args:
            data: DataFrame with features and target
            target_column: Column name for prediction target
            
        Returns:
            Tuple of (sequences, targets)
        """
        sequences = []
        targets = []
        
        # Remove target from features
        feature_columns = [col for col in data.columns if col != target_column]
        
        for i in range(len(data) - self.sequence_length):
            # Get sequence of features
            seq = data[feature_columns].iloc[i:i+self.sequence_length].values
            # Get target (price change at end of sequence)
            target = data[target_column].iloc[i+self.sequence_length]
            
            sequences.append(seq)
            targets.append(target)
        
        return np.array(sequences), np.array(targets)
    
    def normalize_data(
        self,
        sequences: np.ndarray,
        targets: np.ndarray,
        fit: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Normalize sequences and targets
        
        Args:
            sequences: Input sequences
            targets: Target values
            fit: Whether to fit normalization parameters
            
        Returns:
            Normalized sequences and targets
        """
        if fit:
            # Calculate normalization parameters
            self.feature_mean = sequences.mean(axis=(0, 1))
            self.feature_std = sequences.std(axis=(0, 1)) + 1e-8
            self.target_mean = targets.mean()
            self.target_std = targets.std() + 1e-8
        
        # Normalize
        sequences_norm = (sequences - self.feature_mean) / self.feature_std
        targets_norm = (targets - self.target_mean) / self.target_std
        
        return sequences_norm, targets_norm
    
    def train(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame,
        epochs: int = 100,
        batch_size: int = 32,
        early_stopping_patience: int = 15
    ) -> Dict:
        """
        Train the LSTM model
        
        Args:
            train_data: Training dataset
            val_data: Validation dataset
            epochs: Number of training epochs
            batch_size: Batch size
            early_stopping_patience: Patience for early stopping
            
        Returns:
            Training history
        """
        logger.info("Preparing training data...")
        
        # Prepare sequences
        X_train, y_train = self.prepare_sequences(train_data)
        X_val, y_val = self.prepare_sequences(val_data)
        
        # Normalize
        X_train_norm, y_train_norm = self.normalize_data(X_train, y_train, fit=True)
        X_val_norm, y_val_norm = self.normalize_data(X_val, y_val, fit=False)
        
        # Create datasets and loaders
        train_dataset = TimeSeriesDataset(X_train_norm, y_train_norm)
        val_dataset = TimeSeriesDataset(X_val_norm, y_val_norm)
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Training loop
        history = {'train_loss': [], 'val_loss': []}
        best_val_loss = float('inf')
        patience_counter = 0
        
        logger.info(f"Training on {self.device}...")
        
        for epoch in range(epochs):
            # Training phase
            self.model.train()
            train_losses = []
            
            for sequences, targets in train_loader:
                sequences = sequences.to(self.device)
                targets = targets.to(self.device).unsqueeze(1)
                
                # Forward pass
                self.optimizer.zero_grad()
                predictions = self.model(sequences)
                loss = self.criterion(predictions, targets)
                
                # Backward pass
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                
                train_losses.append(loss.item())
            
            # Validation phase
            self.model.eval()
            val_losses = []
            
            with torch.no_grad():
                for sequences, targets in val_loader:
                    sequences = sequences.to(self.device)
                    targets = targets.to(self.device).unsqueeze(1)
                    
                    predictions = self.model(sequences)
                    loss = self.criterion(predictions, targets)
                    val_losses.append(loss.item())
            
            # Calculate epoch metrics
            epoch_train_loss = np.mean(train_losses)
            epoch_val_loss = np.mean(val_losses)
            
            history['train_loss'].append(epoch_train_loss)
            history['val_loss'].append(epoch_val_loss)
            
            # Learning rate scheduling
            self.scheduler.step(epoch_val_loss)
            
            # Early stopping check
            if epoch_val_loss < best_val_loss:
                best_val_loss = epoch_val_loss
                patience_counter = 0
                self.save_model()
            else:
                patience_counter += 1
            
            if epoch % 10 == 0:
                logger.info(
                    f"Epoch {epoch}/{epochs} - "
                    f"Train Loss: {epoch_train_loss:.6f}, "
                    f"Val Loss: {epoch_val_loss:.6f}"
                )
            
            # Early stopping
            if patience_counter >= early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch}")
                break
        
        logger.info(f"Training complete. Best val loss: {best_val_loss:.6f}")
        return history
    
    def predict(
        self,
        recent_data: pd.DataFrame,
        horizon_days: int = 7
    ) -> Dict:
        """
        Make price prediction using trained model
        
        Args:
            recent_data: Recent historical data (at least sequence_length rows)
            horizon_days: Prediction horizon
            
        Returns:
            Prediction with uncertainty estimates
        """
        if len(recent_data) < self.sequence_length:
            raise ValueError(f"Need at least {self.sequence_length} days of data")
        
        self.model.eval()
        
        # Prepare sequence
        feature_columns = [col for col in recent_data.columns if 'price_change' not in col]
        sequence = recent_data[feature_columns].iloc[-self.sequence_length:].values
        
        # Normalize
        sequence_norm = (sequence - self.feature_mean) / self.feature_std
        sequence_tensor = torch.FloatTensor(sequence_norm).unsqueeze(0).to(self.device)
        
        # Predict with Monte Carlo dropout for uncertainty estimation
        self.model.train()  # Enable dropout for MC sampling
        predictions = []
        
        for _ in range(100):  # 100 Monte Carlo samples
            with torch.no_grad():
                pred = self.model(sequence_tensor)
                pred_denorm = pred.cpu().numpy()[0][0] * self.target_std + self.target_mean
                predictions.append(pred_denorm)
        
        self.model.eval()
        
        # Calculate statistics
        predictions = np.array(predictions)
        mean_pred = predictions.mean()
        std_pred = predictions.std()
        
        return {
            'predicted_change_pct': float(mean_pred),
            'uncertainty_std': float(std_pred),
            'confidence_95_lower': float(mean_pred - 1.96 * std_pred),
            'confidence_95_upper': float(mean_pred + 1.96 * std_pred),
            'horizon_days': horizon_days,
            'model_type': 'lstm_attention',
            'monte_carlo_samples': 100,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def save_model(self):
        """Save model and normalization parameters"""
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'feature_mean': self.feature_mean,
            'feature_std': self.feature_std,
            'target_mean': self.target_mean,
            'target_std': self.target_std
        }
        torch.save(checkpoint, self.model_path)
        logger.info(f"Model saved to {self.model_path}")
    
    def load_model(self):
        """Load pre-trained model"""
        checkpoint = torch.load(self.model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.feature_mean = checkpoint['feature_mean']
        self.feature_std = checkpoint['feature_std']
        self.target_mean = checkpoint['target_mean']
        self.target_std = checkpoint['target_std']
        logger.info("Model loaded successfully")
    
    def get_feature_importance(self) -> Dict:
        """
        Estimate feature importance using gradient analysis
        
        Returns:
            Feature importance scores
        """
        self.model.eval()
        
        # Create dummy input
        dummy_input = torch.randn(1, self.sequence_length, self.input_features).to(self.device)
        dummy_input.requires_grad = True
        
        # Forward pass
        output = self.model(dummy_input)
        
        # Backward pass to get gradients
        output.backward()
        
        # Calculate importance as mean absolute gradient
        importance = dummy_input.grad.abs().mean(dim=(0, 1)).cpu().numpy()
        
        return {
            f'feature_{i}': float(imp) 
            for i, imp in enumerate(importance)
        }


if __name__ == "__main__":
    if TORCH_AVAILABLE:
        predictor = DeepLearningPredictor(sequence_length=30, input_features=50)
        print("LSTM Deep Learning Predictor initialized")
        print(f"Device: {predictor.device}")
        print(f"Model parameters: {sum(p.numel() for p in predictor.model.parameters()):,}")
        print("\nModel architecture:")
        print(predictor.model)
    else:
        print("PyTorch not available. Install with: pip install torch")
