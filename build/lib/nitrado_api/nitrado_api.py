import aiohttp
import asyncio
import logging
import json
from ftplib import FTP

class NitradoAPI:
    BASE_URL = "https://api.nitrado.net"

    def __init__(self, nitrado_token):
        self.nitrado_token = nitrado_token
        self.headers = {
            "Authorization": f"Bearer {self.nitrado_token}"
        }
        
    async def _make_request(self, method, endpoint, **kwargs):
        """Auxiliary method to handle API requests with error and rate-limit handling."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self.headers, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 5))
                        logging.warning(f"Rate limit exceeded, retrying in {retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                        return await self._make_request(method, endpoint, **kwargs)
                    else:
                        logging.error(f"Error {response.status}: {await response.text()}")
                        return None
        except aiohttp.ClientError as e:
            logging.error(f"Connection error: {e}")
            return None

    async def get_server_details(self, nitrado_id):
        """Get server details."""
        endpoint = f"/services/{nitrado_id}/gameservers"
        response = await self._make_request("GET", endpoint)
        return response.get("data", {}).get("gameserver") if response else None

    async def restart_server(self, nitrado_id):
        """Restart the game server."""
        endpoint = f"/services/{nitrado_id}/gameservers/restart"
        response = await self._make_request("POST", endpoint)
        return response

    async def stop_server(self, nitrado_id):
        """Stop the game server."""
        endpoint = f"/services/{nitrado_id}/gameservers/stop"
        response = await self._make_request("POST", endpoint)
        return response

    async def manage_list(self, nitrado_id, action, list_type, members):
        """Manage players in whitelist, banlist, or priority list by adding or removing members."""
        endpoint = f"/services/{nitrado_id}/gameservers/settings"
        if list_type not in ["whitelist", "bans", "priority"]:
            raise ValueError("Invalid list type. Use 'whitelist', 'bans', or 'priority'.")
        
        current_settings = await self._make_request("GET", endpoint)
        if not current_settings:
            logging.error("Failed to retrieve current server settings.")
            return None
        
        current_list = current_settings.get("data", {}).get("gameserver", {}).get("settings", {}).get("general", {}).get(list_type, "")
        current_members = set(current_list.split("\r"))

        if action == "add":
            updated_members = current_members.union(members)
        elif action == "remove":
            updated_members = current_members.difference(members)
        else:
            raise ValueError("Invalid action. Use 'add' or 'remove'.")
        
        list_data = {
            "category": "general",
            "key": list_type,
            "value": "\r".join(updated_members)
        }
        
        response = await self._make_request("POST", endpoint, json=list_data)
        return response


    async def get_ftp_credentials(self, nitrado_id):
        """Retrieve FTP credentials from server details."""
        server_details = await self.get_server_details(nitrado_id)
        if server_details:
            return server_details.get("credentials", {}).get("ftp", {})
        return None

    def ftp_connect(self, ftp_details):
        """Establish FTP connection."""
        ftp = FTP()
        ftp.connect(ftp_details["hostname"], int(ftp_details.get("port", 21)))
        ftp.login(ftp_details["username"], ftp_details["password"])
        return ftp

    async def upload_file(self, nitrado_id, filepath, target_path):
        """Upload a file via FTP to the server."""
        ftp_details = await self.get_ftp_credentials(nitrado_id)
        if ftp_details:
            with self.ftp_connect(ftp_details) as ftp:
                with open(filepath, "rb") as file:
                    ftp.storbinary(f"STOR {target_path}", file)
            logging.info(f"File uploaded successfully to {target_path}")
        else:
            logging.error("Failed to retrieve FTP credentials.")

    async def download_file(self, nitrado_id, remote_file_path, local_file_path):
        """Download a file from the server via FTP."""
        ftp_details = await self.get_ftp_credentials(nitrado_id)
        if ftp_details:
            with self.ftp_connect(ftp_details) as ftp:
                with open(local_file_path, "wb") as file:
                    ftp.retrbinary(f"RETR {remote_file_path}", file.write)
            logging.info(f"File downloaded successfully to {local_file_path}")
        else:
            logging.error("Failed to retrieve FTP credentials.")

    async def list_files(self, nitrado_id, directory_path):
        """List files in a specified FTP directory."""
        ftp_details = await self.get_ftp_credentials(nitrado_id)
        if ftp_details:
            with self.ftp_connect(ftp_details) as ftp:
                files = ftp.nlst(directory_path)
                logging.info(f"Files in directory {directory_path}: {files}")
                return files
        else:
            logging.error("Failed to retrieve FTP credentials.")
        return []

    async def schedule_restart(self, nitrado_id, hours):
        """Schedule periodic restarts for the server."""
        endpoint = f"/services/{nitrado_id}/tasks"
        data = {
            "action_method": "game_server_restart",
            "action_data": "",
            "minute": "0",
            "hour": str(hours),
            "day": "*",
            "month": "*",
            "weekday": "*"
        }
        response = await self._make_request("POST", endpoint, json=data)
        return response

    async def validate_file_syntax(self, nitrado_id, file_path):
        """Validate XML/JSON file syntax."""
        local_path = f"/tmp/{file_path.split('/')[-1]}"
        await self.download_file(nitrado_id, file_path, local_path)
        
        file_extension = local_path.split('.')[-1].lower()
        try:
            if file_extension == 'xml':
                import xml.etree.ElementTree as ET
                ET.parse(local_path)
                return "XML syntax is valid"
            elif file_extension == 'json':
                with open(local_path, 'r') as f:
                    json.load(f)
                return "JSON syntax is valid"
        except Exception as e:
            return f"Syntax error in {file_extension.upper()} file: {str(e)}"
        finally:
            import os
            os.remove(local_path)

    async def add_event(self, nitrado_id, event_details):
        """Add a custom event to the server."""
        events_path = "/path/to/events.xml"
        local_path = "/tmp/events.xml"
        await self.download_file(nitrado_id, events_path, local_path)
        
        with open(local_path, "r") as file:
            content = file.read()
        new_event = f"<event name='{event_details['name']}' ... />"
        content = content.replace("</events>", f"{new_event}\n</events>")
        with open(local_path, "w") as file:
            file.write(content)
        
        await self.upload_file(nitrado_id, local_path, events_path)
        logging.info("Event added successfully.")