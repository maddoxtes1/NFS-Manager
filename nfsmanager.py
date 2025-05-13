#!/usr/bin/env python3
import os
import sys
import json
import time
import shutil
import logging
import signal
import atexit
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

PID_FILE = "/var/run/nfsmanager.pid"

class NFSManager:
    def __init__(self, config_file: str = "/etc/nfsmanager/config.json"):
        self.config_file = config_file
        self.log_file = "/var/log/nfsmanager.log"
        self.setup_logging()
        self.running = True

    def setup_logging(self) -> None:
        """Configure le système de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def write_pid_file(self) -> None:
        """Écrit le PID dans le fichier PID"""
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
            self.logger.info(f"PID écrit dans {PID_FILE}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'écriture du fichier PID: {e}")
            sys.exit(1)

    def remove_pid_file(self) -> None:
        """Supprime le fichier PID"""
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
                self.logger.info(f"Fichier PID supprimé: {PID_FILE}")
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression du fichier PID: {e}")

    def is_running(self) -> bool:
        """Vérifie si une instance est déjà en cours d'exécution"""
        try:
            if os.path.exists(PID_FILE):
                with open(PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    # Envoie un signal 0 pour vérifier si le processus existe
                    os.kill(pid, 0)
                    return True
                except OSError:
                    # Le processus n'existe plus, on peut supprimer le fichier PID
                    self.remove_pid_file()
            return False
        except Exception:
            return False

    def stop_running_instance(self) -> bool:
        """Arrête l'instance en cours d'exécution"""
        try:
            if os.path.exists(PID_FILE):
                with open(PID_FILE, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    # Envoie SIGTERM au processus
                    os.kill(pid, signal.SIGTERM)
                    # Attend que le processus se termine (max 10 secondes)
                    for _ in range(10):
                        try:
                            os.kill(pid, 0)
                            time.sleep(1)
                        except OSError:
                            self.logger.info(f"Ancienne instance arrêtée (PID: {pid})")
                            self.remove_pid_file()
                            return True
                    # Si le processus ne répond pas, on force l'arrêt
                    os.kill(pid, signal.SIGKILL)
                    self.logger.warning(f"Ancienne instance forcée à l'arrêt (PID: {pid})")
                    self.remove_pid_file()
                    return True
                except OSError as e:
                    self.logger.error(f"Erreur lors de l'arrêt de l'ancienne instance: {e}")
                    self.remove_pid_file()
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de l'instance en cours: {e}")
            return False

    def signal_handler(self, signum: int, frame: Any) -> None:
        """Gère les signaux pour un arrêt propre"""
        self.logger.info(f"Signal reçu: {signum}")
        self.running = False

    def setup_signal_handlers(self) -> None:
        """Configure les gestionnaires de signaux"""
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        atexit.register(self.cleanup)

    def cleanup(self) -> None:
        """Nettoie les ressources avant l'arrêt"""
        self.logger.info("Nettoyage avant arrêt...")
        self.remove_pid_file()
        # Démontage de tous les partages
        for share in self.read_config():
            self.unmount_share(share)

    def read_config(self) -> List[Dict[str, Any]]:
        """Lit le fichier de configuration JSON et retourne la liste des partages"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config.get('shares', [])
        except FileNotFoundError:
            self.logger.error(f"Fichier de configuration non trouvé: {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Erreur de syntaxe dans le fichier JSON: {e}")
            sys.exit(1)

    def run_command(self, command: List[str], timeout: Optional[int] = None) -> Tuple[int, str, str]:
        """Exécute une commande shell et retourne le code de retour, stdout et stderr"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Commande expirée"
        except Exception as e:
            return -1, "", str(e)

    def is_mounted(self, mount_point: str) -> bool:
        """Vérifie si un point de montage est actuellement monté"""
        try:
            return Path(mount_point).is_mount()
        except Exception:
            return False

    def is_accessible(self, mount_point: str, timeout: int = 5) -> bool:
        """Vérifie si un point de montage est accessible"""
        try:
            code, _, _ = self.run_command(['ls', mount_point], timeout=timeout)
            return code == 0
        except Exception:
            return False

    def clean_directory(self, path: str) -> None:
        """Nettoie un répertoire en supprimant tous ses contenus"""
        try:
            if os.path.exists(path):
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la suppression de {item_path}: {e}")
                self.logger.info(f"Répertoire nettoyé: {path}")
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage du répertoire {path}: {e}")

    def manage_docker(self, container_name: str, action: str) -> bool:
        """Gère les conteneurs Docker (start/stop)"""
        if container_name == "none":
            return True

        try:
            cmd = ['docker', action, container_name]
            code, stdout, stderr = self.run_command(cmd)

            if code == 0:
                self.logger.info(f"Docker {action} réussi pour {container_name}")
                return True
            else:
                self.logger.error(f"Échec du {action} Docker pour {container_name}: {stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la gestion Docker pour {container_name}: {e}")
            return False

    def mount_share(self, share: Dict[str, Any]) -> bool:
        """Monte un partage NFS avec gestion Docker"""
        try:
            server = share.get('server', '')
            remote_path = share.get('remote_path', '')
            local_path = share.get('local_path', '')
            options = share.get('options', '')
            docker = share.get('docker', 'none')
            delete_on_mount = share.get('delete_on_mount', False)

            if not all([server, remote_path, local_path, options]):
                self.logger.error(f"Configuration incomplète pour le partage: {share.get('name', 'unknown')}")
                return False

            # Créer le point de montage s'il n'existe pas
            Path(local_path).mkdir(parents=True, exist_ok=True)

            if self.is_mounted(local_path):
                self.logger.info(f"Le partage {server}:{remote_path} est déjà monté sur {local_path}")
                # Vérifier si le montage existant est accessible
                if not self.is_accessible(local_path):
                    self.logger.warning(f"Le partage monté sur {local_path} n'est pas accessible, tentative de remontage")
                    self.unmount_share(share)
                    time.sleep(2)  # Attendre que le démontage soit terminé
                else:
                    return True

            # Nettoyer le répertoire si demandé
            if delete_on_mount:
                self.clean_directory(local_path)

            # Monter le partage
            cmd = ['mount', '-t', 'nfs', f"{server}:{remote_path}", local_path, '-o', options]
            code, stdout, stderr = self.run_command(cmd)

            if code == 0:
                # Vérifier si le montage est accessible après 5 secondes
                time.sleep(5)
                if not self.is_accessible(local_path):
                    self.logger.error(f"Le montage a réussi mais le partage n'est pas accessible: {local_path}")
                    self.unmount_share(share)
                    return False

                self.logger.info(f"Montage réussi et vérifié: {server}:{remote_path} sur {local_path}")
                # Démarrer Docker si configuré
                if docker != "none":
                    if not self.manage_docker(docker, "start"):
                        self.logger.error(f"Échec du démarrage du conteneur Docker {docker}")
                        return False
                return True
            else:
                self.logger.error(f"Échec du montage de {server}:{remote_path} sur {local_path}: {stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors du montage du partage {share.get('name', 'unknown')}: {e}")
            return False

    def unmount_share(self, share: Dict[str, Any]) -> bool:
        """Démonte un partage NFS avec gestion Docker"""
        try:
            local_path = share.get('local_path', '')
            docker = share.get('docker', 'none')

            if not local_path:
                self.logger.error(f"Chemin local manquant pour le partage: {share.get('name', 'unknown')}")
                return False

            # Arrêter Docker si configuré
            if docker != "none":
                self.manage_docker(docker, "stop")

            if not self.is_mounted(local_path):
                self.logger.info(f"Le partage n'est pas monté sur {local_path}")
                return True

            code, stdout, stderr = self.run_command(['umount', '-f', local_path])

            if code == 0:
                self.logger.info(f"Démontage réussi: {local_path}")
                return True
            else:
                self.logger.error(f"Échec du démontage de {local_path}: {stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors du démontage du partage {share.get('name', 'unknown')}: {e}")
            return False

    def check_shares(self) -> None:
        """Vérifie l'état des partages et les remonte si nécessaire"""
        for share in self.read_config():
            try:
                local_path = share.get('local_path', '')
                if not local_path:
                    self.logger.error(f"Chemin local manquant pour le partage: {share.get('name', 'unknown')}")
                    continue

                # Vérifier si le partage est monté et accessible
                is_mounted = self.is_mounted(local_path)
                is_accessible = self.is_accessible(local_path) if is_mounted else False

                if not is_mounted or not is_accessible:
                    self.logger.info(f"Problème détecté avec le partage sur {local_path}")
                    self.logger.info(f"État: monté={is_mounted}, accessible={is_accessible}")
                    
                    if is_mounted:
                        self.logger.info(f"Démontage du partage inaccessible: {local_path}")
                        self.unmount_share(share)
                        time.sleep(2)
                    
                    if not self.mount_share(share):
                        self.logger.error(f"Échec du remontage du partage: {local_path}")
                        time.sleep(5)  # Attendre avant la prochaine tentative
            except Exception as e:
                self.logger.error(f"Erreur lors de la vérification du partage {share.get('name', 'unknown')}: {e}")

    def start(self) -> None:
        """Démarre le service de surveillance"""
        if self.is_running():
            self.logger.error("Une instance est déjà en cours d'exécution")
            sys.exit(1)

        self.setup_signal_handlers()
        self.write_pid_file()
        self.logger.info("Démarrage du service NFS Manager")

        try:
            while self.running:
                self.check_shares()
                # Vérifie toutes les secondes si on doit s'arrêter
                for _ in range(60):
                    if not self.running:
                        break
                    time.sleep(1)
        except Exception as e:
            self.logger.error(f"Erreur inattendue: {e}")
        finally:
            self.cleanup()

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ['start', 'stop', 'restart']:
        print("Usage: nfsmanager.py {start|stop|restart}")
        sys.exit(1)

    try:
        manager = NFSManager()
        
        if sys.argv[1] == 'start':
            manager.start()
        elif sys.argv[1] == 'stop':
            if manager.is_running():
                manager.stop_running_instance()
            else:
                print("Aucune instance en cours d'exécution")
        elif sys.argv[1] == 'restart':
            if manager.is_running():
                manager.stop_running_instance()
                time.sleep(2)  # Attendre que l'ancienne instance s'arrête
            manager.start()
    except Exception as e:
        print(f"Erreur fatale: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 