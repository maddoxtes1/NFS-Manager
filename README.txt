NFS Manager - Gestionnaire de partages NFS
=========================================

Description
-----------
NFS Manager est un service système qui gère automatiquement le montage et le démontage des partages NFS.
Il inclut des fonctionnalités comme :
- Montage automatique des partages NFS
- Surveillance continue des partages
- Remontage automatique en cas de déconnexion
- Gestion optionnelle des conteneurs Docker
- Nettoyage des répertoires avant montage (optionnel)

Prérequis
---------
- Système d'exploitation : Debian ou dérivé (Ubuntu, etc.)
- Python 3.6 ou supérieur
- Accès root (sudo)
- Client NFS installé (nfs-common)
- Docker (optionnel, uniquement si vous utilisez des conteneurs)

Installation
-----------
1. Téléchargez les fichiers nécessaires :
   - nfsmanager.py
   - nfsmanager.service
   - requirements.txt
   - install.sh

2. Rendez le script d'installation exécutable :
   sudo chmod +x install.sh

3. Lancez l'installation :
   sudo ./install.sh

   Lors de l'installation, vous aurez le choix d'installer Docker ou non.
   Répondez 'o' pour installer Docker, 'n' pour l'ignorer.

Configuration
------------
1. Éditez le fichier de configuration :
   sudo nano /etc/nfsmanager/config.json

2. Exemple de configuration :
   {
       "shares": [
           {
               "name": "seafile",
               "server": "192.168.1.71",
               "remote_path": "/mnt/user/docker_volume/seafile",
               "local_path": "/docker_volume/seafile",
               "options": "rw,sync,hard,intr",
               "docker": "seafile",
               "delete_on_mount": true
           }
       ]
   }

   Options de configuration :
   - name : Nom du partage (pour les logs)
   - server : Adresse IP du serveur NFS
   - remote_path : Chemin sur le serveur NFS
   - local_path : Point de montage local
   - options : Options de montage NFS
   - docker : Nom du conteneur Docker (ou "none")
   - delete_on_mount : true/false pour nettoyer le répertoire avant montage

Commandes de gestion
-------------------
1. Démarrer le service :
   sudo systemctl start nfsmanager

2. Arrêter le service :
   sudo systemctl stop nfsmanager

3. Redémarrer le service :
   sudo systemctl restart nfsmanager

4. Vérifier le statut :
   sudo systemctl status nfsmanager

5. Voir les logs en temps réel :
   sudo journalctl -u nfsmanager -f

6. Voir les logs du fichier :
   sudo tail -f /var/log/nfsmanager.log

7. Vérifier les montages NFS :
   mount | grep nfs

Dépannage
---------
1. Si le service ne démarre pas :
   sudo journalctl -u nfsmanager -n 50

2. Vérifier les permissions :
   ls -l /usr/local/bin/nfsmanager.py
   ls -l /etc/nfsmanager/config.json

3. Vérifier le fichier PID :
   ls -l /var/run/nfsmanager.pid

4. Vérifier les montages :
   df -h | grep nfs

5. Vérifier les conteneurs Docker (si installé) :
   docker ps

Mise à jour
----------
1. Arrêter le service :
   sudo systemctl stop nfsmanager

2. Copier la nouvelle version :
   sudo cp nfsmanager.py /usr/local/bin/
   sudo chmod +x /usr/local/bin/nfsmanager.py

3. Redémarrer le service :
   sudo systemctl start nfsmanager

Désinstallation
--------------
1. Arrêter le service :
   sudo systemctl stop nfsmanager

2. Désactiver le service :
   sudo systemctl disable nfsmanager

3. Supprimer les fichiers :
   sudo rm /usr/local/bin/nfsmanager.py
   sudo rm /etc/nfsmanager/config.json
   sudo rm /etc/systemd/system/nfsmanager.service
   sudo rm /var/run/nfsmanager.pid
   sudo rm /var/log/nfsmanager.log

4. Recharger systemd :
   sudo systemctl daemon-reload

Notes importantes
---------------
- Assurez-vous que les serveurs NFS sont accessibles
- Vérifiez que les chemins de montage existent ou peuvent être créés
- Si vous utilisez Docker, assurez-vous que les conteneurs existent
- Le service doit être exécuté en tant que root
- Les logs sont stockés dans /var/log/nfsmanager.log

Support
-------
En cas de problème :
1. Vérifiez les logs
2. Assurez-vous que les serveurs NFS sont accessibles
3. Vérifiez les permissions des répertoires
4. Vérifiez la configuration dans config.json 
