import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image

# ---------------- CONFIGURATION ----------------
# Point this to where your "Dataset" folder is located
DATA_DIR = r"C:\Users\joshua\Downloads\soil dataset\Dataset" 


TARGET_CLASSES = ["Black Soil", "Red soil", "Yellow Soil"]
BATCH_SIZE = 32
EPOCHS = 5
LEARNING_RATE = 0.0003
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Training on device: {DEVICE}")

# ---------------- CUSTOM DATASET LOADER ----------------
class FilteredSoilDataset(Dataset):
    def __init__(self, root_dir, split="train", transform=None):
        self.samples = []
        self.transform = transform
        self.classes = ["Black Soil", "Red Soil", "Yellow Soil"]
        self.class_to_idx = {cls: idx for idx, cls in enumerate(self.classes)}

        split_dir = os.path.join(root_dir, split)
        if not os.path.exists(split_dir):
            raise FileNotFoundError(f"Cannot find split directory: {split_dir}")

        # Scan for matching folders (case-insensitive)
        for folder in os.listdir(split_dir):
            matched_cls = None
            f_lower = folder.lower()
            if "black" in f_lower:
                matched_cls = "Black Soil"
            elif "red" in f_lower or "laterite" in f_lower:
                matched_cls = "Red Soil"
            elif "yellow" in f_lower:
                matched_cls = "Yellow Soil"

            if matched_cls:
                cls_idx = self.class_to_idx[matched_cls]
                class_folder = os.path.join(split_dir, folder)
                if os.path.isdir(class_folder):
                    for fname in os.listdir(class_folder):
                        if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                            self.samples.append((os.path.join(class_folder, fname), cls_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label

# ---------------- TRANSFORMS ----------------
train_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

val_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# ---------------- LOAD DATA ----------------
print("Loading datasets...")
train_dataset = FilteredSoilDataset(DATA_DIR, split="train", transform=train_transforms)
val_dataset = FilteredSoilDataset(DATA_DIR, split="test", transform=val_transforms)

print(f"Loaded: {len(train_dataset)} training images | {len(val_dataset)} validation images")

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

# ---------------- MODEL INITIALIZATION ----------------
print("Setting up MobileNetV2 architecture...")
model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)

# Replace final classification head with our 3 classes
in_features = model.classifier[1].in_features
model.classifier[1] = nn.Linear(in_features, len(train_dataset.classes))
model = model.to(DEVICE)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

# ---------------- TRAINING LOOP ----------------
for epoch in range(EPOCHS):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in train_loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, preds = torch.max(outputs, 1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

    train_acc = (correct / total) * 100
    avg_loss = running_loss / total

    # Validation
    model.eval()
    val_correct = 0
    val_total = 0
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            outputs = model(images)
            _, preds = torch.max(outputs, 1)
            val_correct += (preds == labels).sum().item()
            val_total += labels.size(0)

    val_acc = (val_correct / val_total) * 100 if val_total > 0 else 0
    print(f"Epoch [{epoch+1}/{EPOCHS}] - Loss: {avg_loss:.4f} | Train Acc: {train_acc:.2f}% | Val Acc: {val_acc:.2f}%")

# ---------------- SAVE MODEL & CLASSES ----------------
torch.save(model.state_dict(), "soil_model.pth")
with open("classes.json", "w") as f:
    json.dump(train_dataset.classes, f)

print("\n Training complete! Saved 'soil_model.pth' and 'classes.json'.")