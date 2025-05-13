#!/bin/bash

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
print_message() {
    echo -e "${2}${1}${NC}"
}

# Vérifier si le script est exécuté en tant que root
if [ "$EUID" -ne 0 ]; then
    print_message "Ce script doit être exécuté en tant que root (sudo)" "$RED"
    exit 1
fi

# Demander si Docker est nécessaire
read -p "Voulez-vous installer Docker ? (o/n) " -n 1 -r
echo
INSTALL_DOCKER=$REPLY

# Vérifier la version de Python
print_message "Vérification de Python..." "$YELLOW"
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version)
    print_message "Python trouvé: $PYTHON_VERSION" "$GREEN"
else
    print_message "Python3 n'est pas installé. Installation..." "$YELLOW"
    apt update && apt install -y python3 python3-pip
fi

# Vérifier pip
print_message "Vérification de pip..." "$YELLOW"
if command -v pip3 &>/dev/null; then
    print_message "pip3 est installé" "$GREEN"
else
    print_message "pip3 n'est pas installé. Installation..." "$YELLOW"
    apt install -y python3-pip
fi

# Vérifier les dépendances système
print_message "Vérification des dépendances système..." "$YELLOW"
DEPS=("nfs-common")
if [[ $INSTALL_DOCKER =~ ^[Oo]$ ]]; then
    DEPS+=("docker.io")
fi

for dep in "${DEPS[@]}"; do
    if ! dpkg -l | grep -q "^ii  $dep "; then
        print_message "Installation de $dep..." "$YELLOW"
        apt install -y "$dep"
    else
        print_message "$dep est déjà installé" "$GREEN"
    fi
done

# Installer les dépendances Python
print_message "Installation des dépendances Python..." "$YELLOW"
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    print_message "Dépendances Python installées" "$GREEN"
else
    print_message "Fichier requirements.txt non trouvé" "$RED"
    exit 1
fi

# Créer les répertoires nécessaires
print_message "Création des répertoires..." "$YELLOW"
mkdir -p /etc/nfsmanager
touch /var/log/nfsmanager.log
chmod 644 /var/log/nfsmanager.log
mkdir -p /var/run

# Créer le fichier config.json d'exemple
print_message "Création du fichier de configuration d'exemple..." "$YELLOW"
cat > /etc/nfsmanager/config.json << 'EOL'
{
    "shares": [
        {
            "name": "exemple_share",
            "server": "192.168.1.100",
            "remote_path": "/mnt/share/exemple",
            "local_path": "/mnt/nfs/exemple",
            "options": "rw,sync,hard,intr",
            "docker": "none",
            "delete_on_mount": false
        },
        {
            "name": "docker_share",
            "server": "192.168.1.100",
            "remote_path": "/mnt/share/docker",
            "local_path": "/mnt/nfs/docker",
            "options": "rw,sync,hard,intr",
            "docker": "mon_conteneur",
            "delete_on_mount": true
        }
    ]
}
EOL

print_message "Fichier de configuration créé. N'oubliez pas de le modifier selon vos besoins." "$YELLOW"

# Copier les fichiers
print_message "Installation des fichiers..." "$YELLOW"
cp nfsmanager.py /usr/local/bin/
chmod +x /usr/local/bin/nfsmanager.py
cp nfsmanager.service /etc/systemd/system/

# Configurer les permissions
print_message "Configuration des permissions..." "$YELLOW"
chown root:root /usr/local/bin/nfsmanager.py
chown root:root /etc/nfsmanager/config.json
chown root:root /etc/systemd/system/nfsmanager.service
chmod 644 /etc/nfsmanager/config.json
chmod 644 /etc/systemd/system/nfsmanager.service

# Activer et démarrer le service
print_message "Configuration du service..." "$YELLOW"
systemctl daemon-reload
systemctl enable nfsmanager
systemctl start nfsmanager

# Vérifier l'installation
print_message "Vérification de l'installation..." "$YELLOW"
if systemctl is-active --quiet nfsmanager; then
    print_message "NFS Manager est installé et en cours d'exécution" "$GREEN"
    print_message "Vous pouvez vérifier les logs avec: sudo journalctl -u nfsmanager -f" "$GREEN"
else
    print_message "Erreur lors du démarrage du service" "$RED"
    print_message "Vérifiez les logs avec: sudo journalctl -u nfsmanager -n 50" "$YELLOW"
fi

print_message "Installation terminée!" "$GREEN"
print_message "N'oubliez pas de configurer votre fichier config.json dans /etc/nfsmanager/" "$YELLOW"
print_message "Un exemple de configuration a été créé avec deux partages :" "$YELLOW"
print_message "1. exemple_share : Un partage simple sans Docker" "$YELLOW"
print_message "2. docker_share : Un partage avec gestion Docker" "$YELLOW"
print_message "Modifiez ces exemples selon vos besoins." "$YELLOW"

# Avertissement si Docker n'est pas installé
if [[ ! $INSTALL_DOCKER =~ ^[Oo]$ ]]; then
    print_message "ATTENTION: Docker n'est pas installé. Les fonctionnalités Docker ne seront pas disponibles." "$YELLOW"
    print_message "Si vous avez besoin de Docker plus tard, installez-le avec: sudo apt install docker.io" "$YELLOW"
fi 