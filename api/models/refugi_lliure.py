from django.db import models
from django.utils import timezone


class RefugiLliure(models.Model):
    TIPUS_CHOICES = [
        ('no guardat', 'No guardat'),
        ('orri', 'Orri'),
        ('ocupat als estius per pastor', 'Ocupat als estius per pastor'),
        ('no guardat als hiverns', 'No guardat als hiverns'),
    ]
    
    ESTAT_CHOICES = [
        ('pobre', 'Pobre'),
        ('normal', 'Normal'),
        ('be', 'Be'),
        ('excellent', 'Excellent'),
    ]
    

    # Atributos principales
    nom = models.CharField(max_length=200, verbose_name="Nom")
    descripcio = models.TextField(verbose_name="Descripció")
    tipus = models.CharField(max_length=20, choices=TIPUS_CHOICES, verbose_name="Tipus")
    imatges = models.JSONField(default=list, blank=True, verbose_name="Imatges")
    
    # Ubicació
    ubicacio = models.CharField(max_length=300, verbose_name="Ubicació")
    regio = models.CharField(max_length=100, verbose_name="Regió")
    altitud = models.IntegerField(verbose_name="Altitud (m)")
    
    # Información del refugio
    capacitat = models.IntegerField(verbose_name="Capacitat")
    estat = models.CharField(max_length=20, choices=ESTAT_CHOICES, default='obert', verbose_name="Estat")
    serveis = models.JSONField(default=list, blank=True, verbose_name="Serveis")
    clau_necessaria = models.BooleanField(default=False, verbose_name="Clau necessària")
    tancat = models.BooleanField(default=False, verbose_name="Tancat")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creat el")
    modified_at = models.DateTimeField(auto_now=True, verbose_name="Modificat el")

    class Meta:
        verbose_name = "Refugi Lliure"
        verbose_name_plural = "Refugis Lliures"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.regio})"

    @property
    def is_available(self):
        """Retorna True si el refugi està disponible per usar"""
        return self.estat == 'obert' and not self.tancat

    def save(self, *args, **kwargs):
        # Actualitzar modified_at quan es guarda
        self.modified_at = timezone.now()
        super().save(*args, **kwargs)