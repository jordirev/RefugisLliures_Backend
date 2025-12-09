✅ 1. Patró Factory Method (versió lleugera)

El mètode:

@classmethod
def from_dict(cls, data: dict)


és un Factory Method, perquè:

crea instàncies de la classe sense que el client hagi de cridar directament al constructor,

encapsula la lògica de creació,

permet crear subclasses sense modificar el codi del client.

Això és EXACTAMENT la idea del Factory Method Pattern.

👉 En aquest cas, és una versió simple, però funcional, del patró.

✅ 2. Patró Template Method (en la part del to_dict)

En RefugeMediaMetadata:

def to_dict(self):
    base = super().to_dict()
    base["creator_uid"] = self.creator_uid
    return base


Aquí:

la classe base proporciona part de l’algorisme (to_dict bàsic),

la subclasse l’amplia amb responsabilitats addicionals.

Això encaixa amb el Template Method Pattern:
La classe base defineix el "template", i les subclasses aporten l'especialització.