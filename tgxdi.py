import asyncio
import time
import os
import json
import getpass
import random
from telethon import TelegramClient, errors
from telethon.tl.types import Channel, Chat, User, InputPeerChannel, InputPeerChat
from telethon.tl import functions, types

class TelegramManager:
    def __init__(self):
        self.client = None
        self.api_id = None
        self.api_hash = None
        self.phone = None
        self.added_count = 0
        self.failed_count = 0
        self.already_member_count = 0
        self.skipped_count = 0
        self.extracted_count = 0
        self.flood_errors = 0
        self.privacy_errors = 0
        self.admin_errors = 0
        self.banned_errors = 0
        self.session_file = 'telegram_session'

    def get_credentials(self):
        """Get API credentials from user input"""
        print("🔐 TELEGRAM API CREDENTIALS SETUP")
        print("=" * 40)
        print("ℹ️  Get your credentials from: https://my.telegram.org")
        print()
        
        # Get API ID
        while True:
            try:
                api_id_input = input("📱 Enter your API ID: ").strip()
                self.api_id = int(api_id_input)
                break
            except ValueError:
                print("❌ API ID must be a number!")
        
        # Get API Hash
        while True:
            api_hash_input = input("🔑 Enter your API Hash: ").strip()
            if len(api_hash_input) >= 30:  # Basic validation
                self.api_hash = api_hash_input
                break
            else:
                print("❌ API Hash seems too short! Please check and try again.")
        
        # Get Phone Number
        while True:
            phone_input = input("📞 Enter your phone number (with country code, e.g., +1234567890): ").strip()
            if phone_input.startswith('+') and len(phone_input) >= 10:
                self.phone = phone_input
                break
            else:
                print("❌ Please enter a valid phone number with country code!")
        
        # Initialize client
        self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
        print("\n✅ Credentials configured successfully!")

    async def start(self):
        """Initialize and start the Telegram client"""
        if not self.client:
            self.get_credentials()
        
        print("\n🔄 Connecting to Telegram...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.client.start(phone=self.phone)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Connection attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(2)
                else:
                    raise e
        
        print("✅ Connected to Telegram successfully!")
        
        # Get current user info (hide sensitive data)
        me = await self.client.get_me()
        phone_display = f"{self.phone[:3]}***{self.phone[-4:]}" if self.phone else "Hidden"
        api_display = f"{str(self.api_id)[:3]}***{str(self.api_id)[-3:]}"
        
        print(f"📱 Logged in as: {me.first_name} {me.last_name or ''}")
        print(f"👤 Username: @{me.username or 'Not set'}")
        print(f"📞 Phone: {phone_display}")
        print(f"🔐 API ID: {api_display}")

    async def get_groups(self, show_details=True):
        """Get all groups/channels the user is part of"""
        if show_details:
            print("\n🔍 Fetching your groups and channels...")
        groups = []
        
        try:
            async for dialog in self.client.iter_dialogs():
                if isinstance(dialog.entity, (Channel, Chat)):
                    group_info = {
                        'id': dialog.entity.id,
                        'title': dialog.entity.title,
                        'entity': dialog.entity
                    }
                    
                    if hasattr(dialog.entity, 'megagroup') and dialog.entity.megagroup:
                        group_info['type'] = 'Supergroup'
                    elif isinstance(dialog.entity, Chat):
                        group_info['type'] = 'Group'
                    elif isinstance(dialog.entity, Channel):
                        if dialog.entity.broadcast:
                            group_info['type'] = 'Channel'
                        else:
                            group_info['type'] = 'Channel'
                    
                    group_info['members'] = getattr(dialog.entity, 'participants_count', 'Unknown')
                    group_info['is_admin'] = dialog.entity.creator or (hasattr(dialog.entity, 'admin_rights') and dialog.entity.admin_rights)
                    groups.append(group_info)
        except Exception as e:
            print(f"❌ Error fetching groups: {e}")
            
        return groups

    def select_group(self, groups, purpose="select"):
        """Let user select a group"""
        if not groups:
            print("❌ No groups found!")
            return None
            
        print(f"\n📋 Found {len(groups)} groups/channels:")
        print("-" * 80)
        
        for i, group in enumerate(groups, 1):
            admin_status = "👑 Admin" if group.get('is_admin') else "👤 Member"
            print(f"{i:2d}. {group['title']}")
            print(f"     Type: {group['type']} | Members: {group['members']} | Status: {admin_status}")
            print()
        
        while True:
            try:
                choice = input(f"Select group to {purpose} (1-{len(groups)}, 0 to cancel): ").strip()
                if choice in ['0', 'q', 'quit', 'exit']:
                    return None
                    
                index = int(choice) - 1
                if 0 <= index < len(groups):
                    selected = groups[index]
                    print(f"\n✅ Selected: {selected['title']}")
                    return selected
                else:
                    print(f"❌ Please enter a number between 1 and {len(groups)}")
            except ValueError:
                print("❌ Please enter a valid number")

    async def extract_members(self, group, save_to_file=True, filename=None):
        """Extract members from a group/channel with enhanced filtering"""
        print(f"\n🔍 Extracting members from '{group['title']}'...")
        
        members = []
        bots_found = 0
        no_username_count = 0
        
        try:
            print("📊 Processing members...")
            async for participant in self.client.iter_participants(group['entity']):
                if isinstance(participant, User):
                    if participant.bot:
                        bots_found += 1
                        continue
                    
                    if not participant.username:
                        no_username_count += 1
                        continue
                    
                    if participant.deleted or participant.restricted:
                        continue
                    
                    member_info = {
                        'id': participant.id,
                        'username': participant.username,
                        'first_name': participant.first_name or '',
                        'last_name': participant.last_name or '',
                        'phone': participant.phone or '',
                        'is_bot': participant.bot,
                        'is_verified': getattr(participant, 'verified', False),
                        'is_premium': getattr(participant, 'premium', False)
                    }
                    
                    members.append(member_info)
                    if len(members) % 50 == 0:
                        print(f"📝 Extracted {len(members)} valid members...")
                    
        except errors.ChatAdminRequiredError:
            print("❌ Admin rights required to view members of this group")
            return []
        except Exception as e:
            print(f"❌ Error extracting members: {e}")
            return []
        
        self.extracted_count = len(members)
        print(f"\n✅ Extraction complete!")
        print(f"📊 Valid members: {len(members)}")
        print(f"🤖 Bots skipped: {bots_found}")
        print(f"👻 No username: {no_username_count}")
        
        if save_to_file and members:
            if not filename:
                safe_title = "".join(c for c in group['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                filename = f"extracted_{safe_title}_{int(time.time())}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# Members extracted from: {group['title']}\n")
                f.write(f"# Extracted on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total valid members: {len(members)}\n")
                f.write(f"# Bots skipped: {bots_found}\n")
                f.write(f"# No username: {no_username_count}\n\n")
                
                for member in members:
                    f.write(f"{member['username']}\n")
            
            print(f"💾 Saved to: {filename}")
            
            # Also save detailed info as JSON
            json_filename = filename.replace('.txt', '_detailed.json')
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(members, f, indent=2, ensure_ascii=False)
            print(f"💾 Detailed info saved to: {json_filename}")
        
        return members

    def load_users(self, filename='members.txt'):
        """Load usernames from file with enhanced validation"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            users = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Clean username
                username = line.lstrip('@').strip()
                if username and len(username) >= 3:  # Minimum username length
                    users.append(username)
                else:
                    print(f"⚠️  Skipped invalid username on line {line_num}: {line}")
            
            print(f"📁 Loaded {len(users)} valid users from {filename}")
            return users
        except FileNotFoundError:
            print(f"❌ File {filename} not found!")
            return []
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")
            return []

    def list_user_files(self):
        """List available user files"""
        print("\n📁 Available user files:")
        print("-" * 50)
        
        files = [f for f in os.listdir('.') if f.endswith('.txt') and 
                (f.startswith('members') or f.startswith('extracted') or f.startswith('users'))]
        
        if not files:
            print("❌ No user files found")
            return None
        
        for i, file in enumerate(files, 1):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                file_size = os.path.getsize(file)
                print(f"{i:2d}. {file} ({len(lines)} users, {file_size} bytes)")
            except:
                print(f"{i:2d}. {file} (error reading)")
        
        while True:
            try:
                choice = input(f"\nSelect file (1-{len(files)}, 0 to cancel): ").strip()
                if choice in ['0', 'q', 'quit']:
                    return None
                
                index = int(choice) - 1
                if 0 <= index < len(files):
                    return files[index]
                else:
                    print(f"❌ Please enter a number between 1 and {len(files)}")
            except ValueError:
                print("❌ Please enter a valid number")

    async def add_user_to_group_optimized(self, username, group):
        """Optimized user adding with maximum success rate"""
        try:
            # Step 1: Resolve user entity with multiple attempts
            user_entity = None
            for attempt in range(3):
                try:
                    if username.startswith('@'):
                        username = username[1:]
                    user_entity = await self.client.get_entity(username)
                    break
                except ValueError:
                    if attempt == 0:
                        try:
                            user_entity = await self.client.get_entity(f"@{username}")
                            break
                        except ValueError:
                            pass
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    return f"❌ User @{username} not found"
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    return f"❌ Error finding @{username}: {str(e)}"

            if not user_entity:
                return f"❌ Could not resolve user @{username}"

            # Skip bots and deleted accounts
            if hasattr(user_entity, 'bot') and user_entity.bot:
                return f"🤖 Skipped @{username} (bot)"
            
            if hasattr(user_entity, 'deleted') and user_entity.deleted:
                return f"👻 Skipped @{username} (deleted account)"

            group_entity = group['entity']
            
            # Step 2: Try adding with appropriate method based on group type
            try:
                if isinstance(group_entity, Channel):
                    if group_entity.megagroup:
                        # Supergroup - use channel invite
                        await self.client(functions.channels.InviteToChannelRequest(
                            channel=group_entity,
                            users=[user_entity]
                        ))
                    else:
                        # Regular channel - usually can't add users
                        return f"❌ Cannot add users to broadcast channel"
                        
                elif isinstance(group_entity, Chat):
                    # Regular group - use add chat user
                    await self.client(functions.messages.AddChatUserRequest(
                        chat_id=group_entity.id,
                        user_id=user_entity,
                        fwd_limit=50
                    ))
                else:
                    return f"❌ Unknown group type for @{username}"
                
                return f"✅ Successfully added @{username}"
                
            except errors.UserAlreadyParticipantError:
                return f"ℹ️  @{username} is already in the group"
                
            except errors.ChatAdminRequiredError:
                return f"🚫 Admin rights required to add @{username}"
                
            except errors.UserPrivacyRestrictedError:
                return f"🔒 @{username} privacy settings prevent adding - will send group link"
                
            except errors.UserNotMutualContactError:
                return f"👥 @{username} must be mutual contact - will send group link"
                
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                print(f"    ⏳ Flood wait: {wait_time}s for @{username}")
                await asyncio.sleep(wait_time + random.randint(1, 3))
                # Retry once after flood wait
                return await self.add_user_to_group_optimized(username, group)
                
            except errors.UserBannedInChannelError:
                return f"🚫 @{username} is banned from this group"
                
            except errors.ChatWriteForbiddenError:
                return f"🚫 No permission to add users to this group"
                
            except errors.UserChannelsTooMuchError:
                return f"📊 @{username} is in too many channels - will send group link"
                
            except errors.PeerFloodError:
                return f"🚫 Peer flood error for @{username} - account limited"
                
            except Exception as e:
                error_msg = str(e)
                if "USER_BLOCKED" in error_msg:
                    return f"🚫 @{username} has blocked you"
                else:
                    return f"❌ Failed to add @{username}: {error_msg}"
                    
        except Exception as e:
            return f"❌ Unexpected error with @{username}: {str(e)}"

    async def send_group_link(self, username, group):
        """Send group link to user who couldn't be added directly"""
        try:
            if username.startswith('@'):
                username = username[1:]
            
            user_entity = await self.client.get_entity(username)
            
            # Get group link
            group_link = f"https://t.me/{group['entity'].username}" if hasattr(group['entity'], 'username') and group['entity'].username else None
            
            if not group_link:
                # Try to get invite link if no public username
                try:
                    if isinstance(group['entity'], Channel):
                        result = await self.client(functions.messages.ExportChatInviteRequest(
                            peer=group['entity']
                        ))
                        group_link = result.link
                except:
                    return f"❌ Could not get link for {group['title']}"
            
            if group_link:
                message = f"Hi! You've been invited to join '{group['title']}'. Click here to join: {group_link}"
                await self.client.send_message(user_entity, message)
                return f"📤 Sent group link to @{username}"
            else:
                return f"❌ Could not get group link for @{username}"
                
        except Exception as e:
            return f"❌ Failed to send link to @{username}: {str(e)}"

    async def add_users_to_group_batch(self, users, group):
        """Batch add users with intelligent delay and progress tracking"""
        if not users:
            print("❌ No users to add!")
            return
            
        print(f"\n🚀 BATCH ADDING - {len(users)} users to '{group['title']}'")
        print("🧠 Using intelligent delay system for maximum success")
        print("=" * 70)
        
        print("\n⚙️  DELAY STRATEGY:")
        print("1. 🏃 Aggressive (1-3s) - Fast but risky")
        print("2. ⚖️  Balanced (3-6s) - Recommended")
        print("3. 🐌 Conservative (8-15s) - Safest")
        print("4. 🧠 Smart Adaptive - AI-like delay adjustment")
        print("5. 🔧 Custom settings")
        
        delay_choice = input("Choose strategy (1-5): ").strip()
        
        if delay_choice == '1':
            base_delay = (1, 3)
            adaptive = False
        elif delay_choice == '2':
            base_delay = (3, 6)
            adaptive = False
        elif delay_choice == '3':
            base_delay = (8, 15)
            adaptive = False
        elif delay_choice == '4':
            base_delay = (2, 8)
            adaptive = True
        elif delay_choice == '5':
            try:
                min_d = float(input("Minimum delay (seconds): "))
                max_d = float(input("Maximum delay (seconds): "))
                base_delay = (min_d, max_d)
                adaptive = input("Use adaptive delays? (y/n): ").lower().startswith('y')
            except ValueError:
                base_delay = (3, 6)
                adaptive = False
        else:
            base_delay = (3, 6)
            adaptive = False
        
        print(f"⏱️  Base delay: {base_delay[0]}-{base_delay[1]}s" + (" (adaptive)" if adaptive else ""))
        
        send_links = input("📤 Send group links to users who can't be added directly? (y/N): ").strip().lower().startswith('y')
        
        consecutive_failures = 0
        consecutive_successes = 0
        recent_flood_errors = 0
        start_time = time.time()
        users_to_send_links = []
        
        for i, username in enumerate(users, 1):
            if not username or username.startswith('#'):
                self.skipped_count += 1
                continue
                
            # Progress indicator
            progress = (i / len(users)) * 100
            elapsed = time.time() - start_time
            eta = (elapsed / i) * (len(users) - i) if i > 0 else 0
            
            print(f"\n[{i}/{len(users)} - {progress:.1f}%] 🎯 Adding @{username}...")
            print(f"    ⏱️  Elapsed: {elapsed/60:.1f}m | ETA: {eta/60:.1f}m")
            
            result = await self.add_user_to_group_optimized(username, group)
            print(f"    {result}")
            
            if "✅ Successfully added" in result:
                self.added_count += 1
                consecutive_failures = 0
                consecutive_successes += 1
            elif "already in the group" in result:
                self.already_member_count += 1
                consecutive_failures = 0
            elif "Skipped" in result and ("bot" in result or "deleted" in result):
                self.skipped_count += 1
            elif "Flood wait" in result:
                self.flood_errors += 1
                recent_flood_errors += 1
                consecutive_failures += 1
                consecutive_successes = 0
            elif "Admin rights required" in result:
                self.admin_errors += 1
                self.failed_count += 1
                consecutive_failures += 1
                consecutive_successes = 0
            elif "privacy settings prevent adding" in result or "must be mutual contact" in result or "too many channels" in result:
                self.privacy_errors += 1
                self.failed_count += 1
                consecutive_failures += 1
                consecutive_successes = 0
                if send_links:
                    users_to_send_links.append(username)
            elif "banned" in result:
                self.banned_errors += 1
                self.failed_count += 1
                consecutive_failures += 1
                consecutive_successes = 0
            else:
                self.failed_count += 1
                consecutive_failures += 1
                consecutive_successes = 0
            
            # Calculate next delay
            if i < len(users):
                if adaptive:
                    # Intelligent delay adjustment
                    if recent_flood_errors >= 2:
                        # Recent flood errors - be very careful
                        wait_time = random.uniform(base_delay[1] * 2, base_delay[1] * 3)
                    elif consecutive_failures >= 5:
                        # Many consecutive failures - slow down significantly
                        wait_time = random.uniform(base_delay[1] * 1.5, base_delay[1] * 2)
                    elif consecutive_successes >= 5:
                        # Many successes - can speed up slightly
                        wait_time = random.uniform(base_delay[0] * 0.8, base_delay[1] * 0.9)
                    elif self.admin_errors > len(users) * 0.3:
                        # Too many admin errors - likely not admin
                        wait_time = random.uniform(base_delay[0], base_delay[1])
                    else:
                        # Normal delay with slight randomization
                        wait_time = random.uniform(base_delay[0], base_delay[1])
                else:
                    # Fixed delay with randomization
                    wait_time = random.uniform(base_delay[0], base_delay[1])
                
                print(f"    ⏳ Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
                
                # Reset flood error counter periodically
                if i % 20 == 0:
                    recent_flood_errors = max(0, recent_flood_errors - 1)
        
        if users_to_send_links and send_links:
            print(f"\n📤 SENDING GROUP LINKS to {len(users_to_send_links)} users...")
            links_sent = 0
            for username in users_to_send_links:
                try:
                    result = await self.send_group_link(username, group)
                    print(f"    {result}")
                    if "Sent group link" in result:
                        links_sent += 1
                    await asyncio.sleep(random.uniform(2, 4))  # Delay between messages
                except Exception as e:
                    print(f"    ❌ Failed to send link to @{username}: {e}")
            
            print(f"✅ Sent {links_sent} group links successfully")
        
        self.print_detailed_summary(len(users))

    def print_detailed_summary(self, total_processed):
        """Print detailed operation summary with analytics"""
        attempted = total_processed - self.skipped_count
        success_rate = (self.added_count / max(1, attempted)) * 100 if attempted > 0 else 0
        
        print("\n" + "=" * 80)
        print("📊 DETAILED OPERATION SUMMARY")
        print("=" * 80)
        print(f"✅ Successfully added:     {self.added_count:4d}")
        print(f"ℹ️  Already members:       {self.already_member_count:4d}")
        print(f"❌ Failed to add:          {self.failed_count:4d}")
        print(f"⏭️  Skipped (bots/empty):   {self.skipped_count:4d}")
        print(f"📤 Previously extracted:   {self.extracted_count:4d}")
        print("-" * 80)
        print("🔍 ERROR BREAKDOWN:")
        print(f"🚫 Admin required:         {self.admin_errors:4d}")
        print(f"🔒 Privacy restricted:     {self.privacy_errors:4d}")
        print(f"⏳ Flood errors:           {self.flood_errors:4d}")
        print(f"🚫 Banned users:           {self.banned_errors:4d}")
        print("-" * 80)
        print(f"📝 Total in file:          {total_processed:4d}")
        print(f"🎯 Actually attempted:     {attempted:4d}")
        print(f"🏆 Success rate:           {success_rate:5.1f}%")
        print("=" * 80)
        
        if success_rate >= 80:
            print("🎉 EXCELLENT! Very high success rate!")
        elif success_rate >= 60:
            print("👍 GOOD! Decent success rate.")
        elif success_rate >= 40:
            print("⚠️  MODERATE success rate.")
        elif success_rate >= 20:
            print("⚠️  LOW success rate.")
        else:
            print("❌ VERY LOW success rate.")
        
        # Specific recommendations based on error types
        if self.admin_errors > attempted * 0.5:
            print("💡 RECOMMENDATION: You likely need admin permissions in the target group")
        if self.privacy_errors > attempted * 0.3:
            print("💡 RECOMMENDATION: Many users have privacy restrictions - try mutual contacts")
        if self.flood_errors > 5:
            print("💡 RECOMMENDATION: Use slower delay settings to avoid flood errors")

    def reset_counters(self):
        """Reset operation counters"""
        self.added_count = 0
        self.failed_count = 0
        self.already_member_count = 0
        self.skipped_count = 0
        self.extracted_count = 0
        self.flood_errors = 0
        self.privacy_errors = 0
        self.admin_errors = 0
        self.banned_errors = 0
        print("🔄 Counters reset - starting fresh count")

    async def run(self):
        """Main execution function with enhanced error handling"""
        try:
            await self.start()
            
            while True:
                self.show_menu()
                choice = input("\nEnter your choice: ").strip()
                
                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '1':
                    self.reset_counters()
                    await self.direct_add_members()

                elif choice == '2':
                    self.reset_counters()
                    await self.direct_extract_members()
                
                elif choice == '3':
                    self.reset_counters()
                    groups = await self.get_groups()
                    
                    print("\n📤 SELECT SOURCE GROUP (to extract from):")
                    source_group = self.select_group(groups, "extract from")
                    if not source_group:
                        continue
                    
                    print("\n📥 SELECT TARGET GROUP (to add to):")
                    target_group = self.select_group(groups, "add to")
                    if not target_group:
                        continue
                    
                    print(f"\n🔄 Will copy members from '{source_group['title']}' to '{target_group['title']}'")
                    confirm = input("Continue? (y/N): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        members = await self.extract_members(source_group, save_to_file=False)
                        if members:
                            usernames = [m['username'] for m in members]
                            await self.add_users_to_group_batch(usernames, target_group)

                elif choice == '4':
                    self.reset_counters()
                    await self.direct_copy_members()
                
                elif choice == '5':
                    groups = await self.get_groups()
                    print(f"\n📋 You are member of {len(groups)} groups/channels")
                
                elif choice == '6':
                    self.list_user_files()
                
                elif choice == '7':
                    me = await self.client.get_me()
                    phone_display = f"{self.phone[:3]}***{self.phone[-4:]}" if self.phone else "Hidden"
                    api_display = f"{str(self.api_id)[:3]}***{str(self.api_id)[-3:]}"
                    
                    print(f"\n⚙️  ACCOUNT INFO:")
                    print(f"👤 Name: {me.first_name} {me.last_name or ''}")
                    print(f"📱 Username: @{me.username or 'Not set'}")
                    print(f"🔐 API ID: {api_display}")
                    print(f"📞 Phone: {phone_display}")
                
                elif choice == '8':
                    print(f"\n📊 PERFORMANCE STATISTICS:")
                    print(f"✅ Total added: {self.added_count}")
                    print(f"❌ Total failed: {self.failed_count}")
                    print(f"ℹ️  Already members: {self.already_member_count}")
                    print(f"📤 Total extracted: {self.extracted_count}")
                    print(f"🚫 Admin errors: {self.admin_errors}")
                    print(f"🔒 Privacy errors: {self.privacy_errors}")
                    print(f"⏳ Flood errors: {self.flood_errors}")
                
                else:
                    print("❌ Invalid choice!")
                
                input("\nPress Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Operation interrupted by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
        finally:
            if self.client:
                await self.client.disconnect()
            print("\n👋 Disconnected from Telegram")

    async def get_group_by_username(self, username):
        """Get group/channel entity by username with enhanced validation"""
        try:
            if not username.startswith('@'):
                username = '@' + username
            
            print(f"🔍 Looking for group: {username}")
            entity = await self.client.get_entity(username)
            
            if isinstance(entity, (Channel, Chat)):
                group_info = {
                    'id': entity.id,
                    'title': entity.title,
                    'entity': entity
                }
                
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    group_info['type'] = 'Supergroup'
                elif isinstance(entity, Chat):
                    group_info['type'] = 'Group'
                elif isinstance(entity, Channel):
                    if entity.broadcast:
                        group_info['type'] = 'Channel'
                    else:
                        group_info['type'] = 'Channel'
                
                group_info['members'] = getattr(entity, 'participants_count', 'Unknown')
                group_info['is_admin'] = entity.creator or (hasattr(entity, 'admin_rights') and entity.admin_rights)
                
                admin_status = "👑 Admin" if group_info['is_admin'] else "👤 Member"
                print(f"✅ Found: {group_info['title']} ({group_info['type']}, {group_info['members']} members, {admin_status})")
                return group_info
            else:
                print(f"❌ {username} is not a group or channel")
                return None
                
        except ValueError:
            print(f"❌ Group/channel {username} not found")
            return None
        except Exception as e:
            print(f"❌ Error finding {username}: {e}")
            return None

    def show_menu(self):
        """Display enhanced main menu"""
        print("\n" + "="*60)
        print("🤖 TELEGRAM MANAGER v4.0 - OPTIMIZED EDITION")
        print("="*60)
        print("1. 📥 Add Members to Group/Channel (Optimized)")
        print("2. 📤 Extract Members from Group/Channel") 
        print("3. 🔄 Copy Members (Extract + Add)")
        print("4. 🎯 Direct Copy (Username → Username)")
        print("5. 📋 View Groups/Channels")
        print("6. 📁 Manage User Files")
        print("7. ⚙️  Settings & Account Info")
        print("8. 📊 Performance Statistics")
        print("0. 🚪 Exit")
        print("="*60)

    async def direct_copy_members(self):
        """Copy members directly using usernames with optimization"""
        print("\n🎯 DIRECT COPY MODE - OPTIMIZED")
        print("=" * 50)
        
        # Get source group username
        source_username = input("📤 Enter SOURCE group/channel username (e.g., @publicgroup): ").strip()
        if not source_username:
            print("❌ Source username required!")
            return
            
        # Get target group username  
        target_username = input("📥 Enter TARGET group/channel username (e.g., @mygroup): ").strip()
        if not target_username:
            print("❌ Target username required!")
            return
        
        # Get source group
        source_group = await self.get_group_by_username(source_username)
        if not source_group:
            return
            
        # Get target group
        target_group = await self.get_group_by_username(target_username)
        if not target_group:
            return
        
        print(f"\n🔄 OPTIMIZED COPY PLAN:")
        print(f"📤 FROM: {source_group['title']} ({source_group['type']})")
        print(f"📥 TO:   {target_group['title']} ({target_group['type']})")
        
        if not target_group.get('is_admin'):
            print("⚠️  WARNING: You don't appear to be admin in target group - success rate may be low")
        
        confirm = input("\n✅ Proceed with optimized copying? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Operation cancelled")
            return
            
        # Extract members from source
        print(f"\n📤 STEP 1: Extracting members from {source_group['title']}")
        members = await self.extract_members(source_group, save_to_file=False)
        
        if not members:
            print("❌ No members extracted!")
            return
            
        # Add members to target with optimization
        print(f"\n📥 STEP 2: Adding {len(members)} members to {target_group['title']} (OPTIMIZED)")
        usernames = [m['username'] for m in members if m['username']]
        
        if usernames:
            await self.add_users_to_group_batch(usernames, target_group)
        else:
            print("❌ No valid usernames found!")

    async def direct_add_members(self):
        """Add members directly to username with optimization"""
        print("\n📥 DIRECT ADD MODE - OPTIMIZED")
        print("=" * 50)
        
        # Get target group username
        target_username = input("📥 Enter target group/channel username (e.g., @mygroup): ").strip()
        if not target_username:
            print("❌ Username required!")
            return
            
        # Get target group
        target_group = await self.get_group_by_username(target_username)
        if not target_group:
            return
        
        print(f"\n📥 OPTIMIZED ADD TO: {target_group['title']} ({target_group['type']})")
        
        if not target_group.get('is_admin'):
            print("⚠️  WARNING: You don't appear to be admin - success rate may be low")
        
        # Get users to add
        print("\n📝 USER INPUT OPTIONS:")
        print("1. Load from file")
        print("2. Enter usernames manually")
        
        input_choice = input("Choose input method (1-2): ").strip()
        users = []
        
        if input_choice == '1':
            filename = self.list_user_files()
            if filename:
                users = self.load_users(filename)
        elif input_choice == '2':
            print("Enter usernames (one per line, empty line to finish):")
            while True:
                username = input("Username: ").strip().lstrip('@')
                if not username:
                    break
                users.append(username)
        
        if not users:
            print("❌ No users to add!")
            return
        
        print(f"\n✅ Will add {len(users)} users to {target_group['title']} (OPTIMIZED)")
        confirm = input("Proceed? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            await self.add_users_to_group_batch(users, target_group)

    async def direct_extract_members(self):
        """Extract members directly using username"""
        print("\n📤 DIRECT EXTRACT MODE")
        print("=" * 40)
        
        # Get source group username
        source_username = input("📤 Enter group/channel username to extract from (e.g., @publicgroup): ").strip()
        if not source_username:
            print("❌ Username required!")
            return
            
        # Get source group
        source_group = await self.get_group_by_username(source_username)
        if not source_group:
            return
        
        print(f"\n📤 EXTRACT FROM: {source_group['title']} ({source_group['type']})")
        
        confirm = input("\n✅ Proceed with extraction? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Operation cancelled")
            return
            
        # Extract members
        await self.extract_members(source_group, save_to_file=True)

def main():
    """Entry point"""
    print("🤖 TELEGRAM MANAGER v4.0 - OPTIMIZED EDITION")
    print("=" * 60)
    print("🚀 NEW FEATURES:")
    print("   • 🧠 Intelligent delay system with AI-like adaptation")
    print("   • 📊 Detailed error analytics and recommendations")
    print("   • ⚡ Optimized adding algorithms for higher success")
    print("   • 🔍 Enhanced user validation and filtering")
    print("   • 📈 Real-time progress tracking with ETA")
    print("   • 🛡️  Advanced flood protection and retry logic")
    print("=" * 60)
    
    if not os.path.exists('members.txt'):
        print("📝 Creating sample members.txt file...")
        sample_content = """# Add usernames here (one per line)
# Lines starting with # are ignored
# Minimum 3 characters per username
# 
# Examples (remove # to use):
# john_doe
# alice_smith
# bob_wilson
#
# Add your actual usernames below:

"""
        
        with open('members.txt', 'w', encoding='utf-8') as f:
            f.write(sample_content)
        
        print("✅ Created members.txt with examples")
    
    manager = TelegramManager()
    asyncio.run(manager.run())

if __name__ == "__main__":
    main()
