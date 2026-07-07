"""File classification: decide which folder a file belongs in."""

from downloads_organizer.classifier.base import Classification, Classifier
from downloads_organizer.classifier.chain import ClassifierChain
from downloads_organizer.classifier.content import ContentTypeClassifier
from downloads_organizer.classifier.extension import ExtensionClassifier

__all__ = [
    "Classification",
    "Classifier",
    "ClassifierChain",
    "ContentTypeClassifier",
    "ExtensionClassifier",
]
