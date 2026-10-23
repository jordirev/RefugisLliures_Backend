# Model de domini UML "Refus" (traducció per a LLM)

Font: diagrama draw.io `Refus_UML.drawio`. Aquest document descriu el model de classes en dos formats equivalents:
1. Un `classDiagram` de Mermaid (llegible per màquina).
2. Una descripció textual de classes, enumeracions i relacions.

Context: l'aplicació gestiona **refugis de muntanya** (`Refugi`), **usuaris** (`Usuari`) i el contingut que aporten (visites, reformes, dubtes i respostes, experiències, fotos i propostes de canvi).

---

## 1. Diagrama Mermaid

```mermaid
classDiagram
    direction LR

    class Refugi {
        +String id
        +String nom
        +String sobrenom [0..1]
        +TRefuge tipus
        +String descripcio
        +Coordinates coordenades
        +String regio [0..1]
        +Integer altitud
        +Integer capacitat [0..1]
        +TEstat estat [0..1]
        +Map~String, bool~ serveis
        +Url links [*]
        +Date modifiedAt
    }

    class Usuari {
        +String uid
        +String username
        +email email
        +TIdioma idioma
        +String[] favouriteRefuges
        +Integer numSharedExperiences
        +Integer numRenovatedRefuges
        +Date createdAt
    }

    class Visita {
        +Date data
        +Integer numVisitants
    }

    class ReformaRefugi {
        +String id
        +Date dataIni
        +Date dataFi
        +String descripcio
        +String[] materialNecessari [*]
        +String[] linkGrup [*]
    }

    class dubte {
        +String id
        +String missatge
        +Time createdAt
    }

    class resposta {
        +String id
        +String missatge
        +Time createdAt
    }

    class ExperienciaUsuari {
        +String id
        +String comentari
        +Time modifiedAt
    }

    class PropostaDeRefugi {
        +String id
        +TAction action
        +TStatus status
        +Map payload [0..1]
        +String comment [0..1]
        +Map refugeSnapshot [0..1]
        +String createdAt
        +String reviewedAt [0..1]
        +String rejectionReason [0..1]
    }

    class MediaMetadata {
        +String key
        +String url
        +Date updloadedAt
    }

    class RefugiMediaMetadata

    class Coordinates {
        <<dataType>>
        +Float latitud
        +Float longitud
    }
    class TEstat {
        <<enumeration>>
        Pobre
        Correcte
        Bé
        Excel·lent
    }
    class TRefugi {
        <<enumeration>>
        Orri
        No guardat
        Ocupat als estius per pastor
        Tancat
        Emergencia
    }
    class TStatus {
        <<enumeration>>
        Pending
        Approved
        Rejected
    }
    class TAction {
        <<enumeration>>
        Create
        Update
        Delete
    }

    %% L'ordre (origen -> destí) de cada relació guia el disseny automàtic:
    %% esquerra: MediaMetadata/RefugiMediaMetadata | Refugi
    %% centre:   Visita, ReformaRefugi, dubte, resposta, ExperienciaUsuari, PropostaDeRefugi
    %% dreta:    Usuari
    %% Les enumeracions i Coordinates queden soltes, com a l'original (sense fletxes).

    %% Fitxers (esquerra)
    MediaMetadata <|-- RefugiMediaMetadata : Tipus {disjoint, complete}
    RefugiMediaMetadata "*" -- "1" Refugi

    %% Refugi -> classes del centre
    Refugi "1" -- "*" Visita
    Refugi "1" -- "*" ReformaRefugi
    Refugi "1" -- "*" dubte
    Refugi "1" -- "*" ExperienciaUsuari
    Refugi "0..1" -- "*" PropostaDeRefugi

    %% Classes del centre -> Usuari
    Visita "*" -- "1" Usuari : indica
    ReformaRefugi "*" -- "0..1" Usuari : crea
    ReformaRefugi "*" -- "*" Usuari : s'uneix
    dubte "*" -- "1" Usuari : pregunta
    resposta "*" -- "1" Usuari : contesta
    ExperienciaUsuari "*" -- "1" Usuari : comparteix
    PropostaDeRefugi "*" -- "0..1" Usuari : proposa canvis
    PropostaDeRefugi "*" -- "*" Usuari : l'admin revisa

    %% Dubtes i respostes
    dubte "1" -- "*" resposta : es contestat
    resposta "0..*" -- "0..1" resposta : respon

    %% Experiència -> fitxers
    RefugiMediaMetadata "*" -- "0..1" ExperienciaUsuari : adjunta

    %% Relacions directes Refugi - Usuari i fitxers de l'usuari
    Refugi "*" -- "*" Usuari : ha visitat
    Refugi "*" -- "*" Usuari : guarda a preferits
    RefugiMediaMetadata "*" -- "1" Usuari : penja fotos
    MediaMetadata "0..1" -- "1" Usuari : puja avatar
```

---

## 2. Descripció textual

### Classes
- **Refugi**: refugi de muntanya. Té `tipus` (enum `TRefugi`), `coordenades` (`Coordinates`), `estat` opcional (enum `TEstat`), `serveis` (mapa nom de servei → booleà), `links` (llista d'URLs) i `modifiedAt`. Opcionals: `sobrenom`, `regio`, `capacitat`, `estat`.
- **Usuari**: persona registrada. Té `uid`, `username`, `email`, `idioma` (`TIdioma`), llista de refugis preferits (`favouriteRefuges`) i comptadors `numSharedExperiences` i `numRenovatedRefuges`.
- **Visita**: registre d'una visita a un refugi (`data`, `numVisitants`).
- **ReformaRefugi**: reforma d'un refugi amb dates d'inici/fi, descripció, material necessari i enllaços del grup.
- **dubte** / **resposta**: pregunta d'un usuari sobre un refugi i les respostes que rep. Les respostes poden respondre a altres respostes (associació reflexiva).
- **ExperienciaUsuari**: comentari/experiència que un usuari comparteix sobre un refugi.
- **PropostaDeRefugi**: proposta de canvi (crear/actualitzar/eliminar) sobre un refugi; un administrador la revisa. `payload` conté els canvis, `refugeSnapshot` una còpia de l'estat del refugi, `status` el resultat (`Pending`/`Approved`/`Rejected`).
- **MediaMetadata**: metadades d'un fitxer (`key`, `url`, `updloadedAt`). Especialitzada per **RefugiMediaMetadata** (fotos associades a un refugi), restricció `{disjoint, complete}`.

### Enumeracions i tipus
- `TEstat`: Pobre, Correcte, Bé, Excel·lent
- `TRefugi`: Orri, No guardat, Ocupat als estius per pastor, Tancat, Emergencia
- `TStatus`: Pending, Approved, Rejected
- `TAction`: Create, Update, Delete
- `Coordinates` (dataType): latitud: Float, longitud: Float
- `TIdioma`: usat per `Usuari.idioma` però **no definit** al diagrama.

### Relacions (multiplicitat en cada extrem)

| Extrem A | Etiqueta | Extrem B |
|---|---|---|
| Usuari * | ha visitat | * Refugi |
| Usuari * | guarda a preferits | * Refugi |
| Refugi 1 | (sense etiqueta) | * Visita |
| Usuari 1 | indica | * Visita |
| Refugi 1 | (sense etiqueta) | * ReformaRefugi |
| Usuari 0..1 | crea | * ReformaRefugi |
| Usuari * | s'uneix | * ReformaRefugi |
| Refugi 1 | (sense etiqueta) | * dubte |
| Usuari 1 | pregunta | * dubte |
| dubte 1 | es contestat | * resposta |
| Usuari 1 | contesta | * resposta |
| resposta 0..* | respon | 0..1 resposta |
| Refugi 1 | (sense etiqueta) | * ExperienciaUsuari |
| Usuari 1 | comparteix | * ExperienciaUsuari |
| ExperienciaUsuari 0..1 | adjunta | * RefugiMediaMetadata |
| Refugi 1 | (sense etiqueta) | * RefugiMediaMetadata |
| Usuari 1 | penja fotos | * RefugiMediaMetadata |
| Usuari 1 | puja avatar | 0..1 MediaMetadata |
| Refugi 0..1 | (sense etiqueta) | * PropostaDeRefugi |
| Usuari 0..1 | proposa canvis | * PropostaDeRefugi |
| Usuari * | l'admin revisa | * PropostaDeRefugi |
| MediaMetadata | herència {disjoint, complete}, "Tipus" | RefugiMediaMetadata |

### Notes i possibles incoherències del diagrama original
- `TIdioma` no està definit; el tipus `email` s'usa com a tipus d'atribut.
- `Refugi.tipus` es declara com `TRefuge`, però l'enumeració es diu `TRefugi`.
- `MediaMetadata.updloadedAt` té una errada ortogràfica (`uploadedAt`); `<< enummeration>>` també (`enumeration`).
- `PropostaDeRefugi.createdAt`, `reviewedAt` són `String`, mentre la resta de dates són `Date`/`Time`.
- Les multiplicitats de les relacions de `PropostaDeRefugi` amb `Usuari` s'han llegit visualment (`0..1` per "proposa canvis" i `*`–`*` per "l'admin revisa") i convé confirmar-les.
