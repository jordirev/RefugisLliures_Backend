A partir dels documents passats, crea les views, controllers, serializers i daos per a poder fer el següent:
en el serializer, a part de totes les configuracions, fes que la data només es vegi amb la data i no amb el time.

a la renovation_views:
GET renovations/ per a obtenir totes les renovations
POST renovation/ per a crear una renovation (no es poden solapar temporalment amb altres renovations del mateix refugi) (guardar en el usuari el id de la reforma un cop creada en un camp opcional anomenat created_renovations; fes els canvis en el model, serializer...)
PATCH renovation/ per a editar una renovation (només si el uid del usuari és el mateix que creator_uid) (el refuge_id i el creator_uid no poden ser editats) (si s'edita la data, comprovar solapaments temporals igual que a l'hora de crear la renovation)
DELETE renovation/ per a eliminar una renovation (només si el uid del usuari és el mateix que creator_uid) (s'elimina el id de la llista created_renovations)

a més,
POST renovations/{id}/participants per a afegir un participant (s'haurà de guardar la id de la refroma a l'usuari, com a joined_renovations)
DELETE renovations/{id}/participants/{uid} per a edliminar un participant
Un creador no pot unirse a una refroma seva. (s'elimina el id de la llista de joined_renovations)

a més,
GET users/uid/renovations ha d'obtenir totes les renovations de l'usuari (tant les creades com les unides) fent crides a tarves dels llistats que tindrà guardat com a parametres joined_renovations i created_renovations.

GET refuges/id/renovations haurà d'obtenir totes les refromes que estan actives d'un refugi (és a dir, que la ini_date encara no ha passat). Per fer-ho es comptara amb un index sobre els camps refuge_id i ini_date

totes seran amb permisos isAuthenticated i crea un permis (si no esta per defecte en el spermisos de drf) que sigui isCreator o algo semblant que comprovi el creator_id del objecte i el uid del usuari que ha fet la crida al endpoint.

