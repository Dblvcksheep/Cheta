import json
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from Crypto.Cipher import AES
import base64
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
from .models import Wallet, Subscribe
import requests
import os
from dotenv import load_dotenv

load_dotenv()

pinata_access_token = os.environ['PINATA_ACCESS']
pinata_url = os.environ['PINATA_URL']
pinata_headers = {
    "Authorization": f"Bearer {pinata_access_token}",
}

Account.enable_unaudited_hdwallet_features()
encryption_key =os.environ['ENCRYPTION_KEY'].encode()
mint_signer_key = os.environ['MINT_SIGNER']


SUBSCRIPTION_ADDRESS=Web3.to_checksum_address(os.environ['SUBSCRIPTION_ADDRESS'])

CONTRACT_ADDRESS = Web3.to_checksum_address(os.environ['CONTRACT_ADDRESS'])

BASE_RPC = os.environ['BASE_RPC']
w3 = Web3(Web3.HTTPProvider(BASE_RPC))

USDC_ADDRESS = Web3.to_checksum_address(os.environ['USDC_ADDRESS'])
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [],
        "type": "function"
    },

]
CERT_ABI =[
  {
    "inputs": [
      { "internalType": "uint256", "name": "courseId", "type": "uint256" },
      { "internalType": "string", "name": "tokenURI_", "type": "string" },
      { "internalType": "bytes", "name": "signature", "type": "bytes" }
    ],
    "name": "mintCertificate",
    "outputs": [
      { "internalType": "uint256", "name": "", "type": "uint256" }
    ],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "address", "name": "", "type": "address" },
      { "internalType": "uint256", "name": "", "type": "uint256" }
    ],
    "name": "hasMintedCourse",
    "outputs": [
      { "internalType": "bool", "name": "", "type": "bool" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "signer",
    "outputs": [
      { "internalType": "address", "name": "", "type": "address" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "tokenId", "type": "uint256" }
    ],
    "name": "getOriginalMinter",
    "outputs": [
      { "internalType": "address", "name": "", "type": "address" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "tokenId", "type": "uint256" }
    ],
    "name": "tokenURI",
    "outputs": [
      { "internalType": "string", "name": "", "type": "string" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "user", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": True, "name": "courseId", "type": "uint256"},
            {"indexed": False, "name": "tokenURI", "type": "string"}
        ],
        "name": "CertificateMinted",
        "type": "event"
    },
    {
      "anonymous": False,
      "inputs": [
        {"indexed": True, "name": "from", "type": "address"},
        {"indexed": True, "name": "to", "type": "address"},
        {"indexed": True, "name": "tokenId", "type": "uint256"}
      ],
      "name": "Transfer",
      "type": "event"
    },
    {
      "anonymous": False,
      "inputs": [
        {"indexed": True, "name": "owner", "type": "address"},
        {"indexed": True, "name": "approved", "type": "address"},
        {"indexed": True, "name": "tokenId", "type": "uint256"}
      ],
      "name": "Approval",
      "type": "event"
    },
    {
      "anonymous": False,
      "inputs": [
        {"indexed": True, "name": "owner", "type": "address"},
        {"indexed": True, "name": "operator", "type": "address"},
        {"indexed": False, "name": "approved", "type": "bool"}
      ],
      "name": "ApprovalForAll",
      "type": "event"
    },
    {
      "anonymous": False,
      "inputs": [
        {"indexed": True, "name": "previousOwner", "type": "address"},
        {"indexed": True, "name": "newOwner", "type": "address"}
      ],
      "name": "OwnershipTransferred",
      "type": "event"
    },
    {
        "type": "function",
        "name": "setSigner",
        "inputs": [
            {"name": "newSigner", "type": "address"}
        ],
        "outputs": [],
        "stateMutability": "nonpayable"
    },
    {
      "name": "ownerOf",
      "type": "function",
      "stateMutability": "view",
      "inputs": [{"name": "tokenId", "type": "uint256"}],
      "outputs": [{"name": "", "type": "address"}]
    },
]


usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CERT_ABI)

def generate_certificate(name, course, cert_id,score,output_path, txhash=None):
    # Canvas sizee
    width, height = 1400, 900

    # Colors
    bg_color = "#fffdf5"  # off-white (like paper)
    text_color = "#222222"
    gold = "#c6a240"      # elegant gold accent
    gray = "#555555"

    # Create background
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Fonts (replace with custom TTFs for more style)
    title_font = ImageFont.truetype("arialbd.ttf", 70)
    name_font = ImageFont.truetype("arialbd.ttf", 60)
    course_font = ImageFont.truetype("arial.ttf", 46)
    small_font = ImageFont.truetype("arial.ttf", 32)
    meta_font = ImageFont.truetype("arial.ttf", 28)
    brand_font = ImageFont.truetype("arialbd.ttf", 52)

    # Border
    border = 12
    draw.rectangle([(border, border), (width - border, height - border)],
                   outline=gold, width=border)

    # Logo Text
    brand_text = "Cheta"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, 70),
              brand_text, fill=gold, font=brand_font)

    # Title
    title = "Certificate of Completion"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, 180),
              title, fill=text_color, font=title_font)

    # Body
    body_text = "This is to certify that"
    bbox = draw.textbbox((0, 0), body_text, font=small_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, 320),
              body_text, fill=text_color, font=small_font)

    # Learner’s name (bold, centered)
    bbox = draw.textbbox((0, 0), name, font=name_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, 390),
              name, fill=gold, font=name_font)

    # Course line
    line1 = "has successfully completed the course"
    bbox = draw.textbbox((0, 0), line1, font=small_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, 480),
              line1, fill=text_color, font=small_font)

    # Course name (centered, accent)
    bbox = draw.textbbox((0, 0), course, font=course_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, 540),
              course, fill=gold, font=course_font)

    draw.text((180, height - 210), f"Scored {score}% on Technical Assessments",
              fill=gray, font=meta_font)
    # Metadata
    issued_date = datetime.now().strftime("%B %d, %Y")
    draw.text((180, height - 180), f"Issued on: {issued_date}",
              fill=gray, font=meta_font)
    draw.text((180, height - 150), f"Certificate TokenId: {cert_id}",
              fill=gray, font=meta_font)
    draw.text((180, height - 120), f"Transaction Hash: {txhash}",
              fill=gray, font=meta_font)
    # Footer / Signature
    footer_text = "Authorized by Cheta.xyz"
    bbox = draw.textbbox((0, 0), footer_text, font=meta_font)
    draw.text(((width - (bbox[2]-bbox[0]))/2, height - 80),
              footer_text, fill=gold, font=meta_font)

    img.save(output_path)
    print(f"✅ Udemy-style certificate saved: {output_path}")
    return output_path


def encrypt_private_key(private_key):
    cipher = AES.new(encryption_key, AES.MODE_EAX)
    nonce = cipher.nonce
    ciphertext, tag = cipher.encrypt_and_digest(private_key.encode())
    return base64.b64encode(nonce + tag + ciphertext).decode()

def decrypt_private_key(enc_private_key):
    data = base64.b64decode(enc_private_key)
    nonce, tag, ciphertext = data[:16], data[16:32], data[32:]
    cipher = AES.new(encryption_key, AES.MODE_EAX, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag).decode()

def create_wallet_for_new_user(instance):
    # Generate wallet
    acct, mnemonic= Account.create_with_mnemonic()

    Wallet.objects.create(
        user=instance,
        wallet=acct.address,
        p_key=encrypt_private_key(acct.key.hex()),
    )

def connect_wallet(user):
    try:
        wallet = Wallet.objects.get(user=user)
    except Wallet.DoesNotExist:
        return None

    private_key = decrypt_private_key(wallet.p_key)
    acct = Account.from_key(private_key)
    return acct

def check_usdc_balance(acct, amount):
    """
    acct: Account object from eth_account (Account.from_key)
    amount: float or int (e.g. 10 for 10 USDC)
    """

    wallet_address = acct.address

    # Get balance
    balance = usdc_contract.functions.balanceOf(wallet_address).call()
    decimals = usdc_contract.functions.decimals().call()

    # Convert human amount to token units
    required_amount = int(amount * (10 ** decimals))

    # Compare
    has_funds = balance >= required_amount

    return {
        "wallet": wallet_address,
        "balance_raw": balance,
        "balance_usdc": balance / (10 ** decimals),
        "required_usdc": amount,
        "has_enough": has_funds,
    }

def check_eth_balance(acct, amount):
    """
    acct: Account object from eth_account (Account.from_key)
    amount: float or int (e.g. 0.05 for 0.05 ETH)
    """

    wallet_address = acct.address

    # Get balance in wei
    balance_wei = w3.eth.get_balance(wallet_address)

    # Convert human amount to wei
    required_wei = Web3.to_wei(amount, "ether")

    # Compare
    has_funds = balance_wei >= required_wei

    return {
        "wallet": wallet_address,
        "balance_raw": balance_wei,
        "balance_eth": float(Web3.from_wei(balance_wei, "ether")),
        "required_eth": amount,
        "has_enough": has_funds,
    }

def direct_usdc_transfer(user_acct, amount):
    """
    Direct USDC transfer (user pays gas)
    Handles all errors and returns a clear result.
    """

    try:
        web3 = w3
        decimals = 6
        amount_wei = int(amount * (10 ** decimals))

        # Build transaction
        tx = usdc_contract.functions.transfer(
            SUBSCRIPTION_ADDRESS,
            amount_wei
        ).build_transaction({
            "from": user_acct.address,
            "nonce": web3.eth.get_transaction_count(user_acct.address),
            "gas": 120000,
            "gasPrice": web3.eth.gas_price,
            "chainId": web3.eth.chain_id,
        })

        # Sign with user key
        signed_tx = user_acct.sign_transaction(tx)

        # Send
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # --- SUCCESS / FAILURE CHECK ---
        if receipt.status == 1:
            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "receipt": receipt
            }
        else:
            # Transaction was mined but REVERTED
            return {
                "success": False,
                "error": "Transaction reverted",
                "tx_hash": tx_hash.hex(),
                "receipt": receipt
            }

    except Exception as e:
        # Any send/sign/build error
        return {
            "success": False,
            "error": str(e),
            "receipt": None
        }


def send_usdc(user_acct,amount,receiver):
    try:
        web3 = w3

        receiver = Web3.to_checksum_address(receiver)
        decimals = 6
        amount_wei = int(amount * (10 ** decimals))

        # Build transaction
        tx = usdc_contract.functions.transfer(
            receiver,
            amount_wei
        ).build_transaction({
            "from": user_acct.address,
            "nonce": web3.eth.get_transaction_count(user_acct.address),
            "chainId": web3.eth.chain_id,
        })

        # Sign with user key
        signed_tx = user_acct.sign_transaction(tx)

        # Send
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # --- SUCCESS / FAILURE CHECK ---
        if receipt.status == 1:
            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "receipt": receipt
            }
        else:
            # Transaction was mined but REVERTED
            return {
                "success": False,
                "error": "Transaction reverted",
                "tx_hash": tx_hash.hex(),
                "receipt": receipt
            }

    except Exception as e:
        # Any send/sign/build error
        return {
            "success": False,
            "error": str(e),
            "receipt": None
        }


def send_eth(user_acct, amount, receiver):
    """
    Send Base ETH from a user's custodial wallet without specifying gas.

    Args:
        user_acct: Local account object with private key (custodial)
        amount: float, ETH amount to send
        receiver: str, recipient address

    Returns:
        dict with success, tx_hash, receipt or error
    """
    receiver = Web3.to_checksum_address(receiver)
    try:
        web3 = w3  # your Web3 instance connected to Base

        # Convert ETH to Wei
        amount_wei = int(amount * 10 ** 18)

        # Build transaction (gas/gasPrice omitted)
        tx = {
            "from": user_acct.address,
            "to": receiver,
            "value": amount_wei,
            "nonce": web3.eth.get_transaction_count(user_acct.address),
            "gas": 21000,
            "gasPrice": w3.eth.gas_price,
            "chainId": web3.eth.chain_id,
        }

        # Sign the transaction
        signed_tx = user_acct.sign_transaction(tx)

        # Send raw transaction
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for receipt
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status == 1:
            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "receipt": receipt
            }
        else:
            return {
                "success": False,
                "error": "Transaction reverted",
                "tx_hash": tx_hash.hex(),
                "receipt": receipt
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "receipt": None
        }
    
def sign_certificate_message(user_address: str, course_id: int, token_uri: str) -> str:
    """
    Sign a certificate mint request to authorize a user to mint an SBT.

    Args:
        signer_private_key: The private key of the authorized signer (0x prefixed hex string)
        user_address: The address of the user who will mint (0x prefixed)
        course_id: The course ID for the certificate
        token_uri: The metadata URI for the token

    Returns:
        The signature as a hex string (0x prefixed)
    """
    # Ensure addresses are checksummed
    user_address = Web3.to_checksum_address(user_address)

    # Encode the message hash exactly as in the contract:
    # keccak256(abi.encodePacked(msg.sender, courseId, tokenURI_))
    message_hash = Web3.solidity_keccak(
        ['address', 'uint256', 'string'],
        [user_address, course_id, token_uri]
    )

    # Create the Ethereum signed message
    # This adds the "\x19Ethereum Signed Message:\n32" prefix
    signable_message = encode_defunct(primitive=message_hash)

    # Sign the message
    account = Account.from_key(mint_signer_key)
    signed_message = account.sign_message(signable_message)

    # Return the signature as a hex string
    return signed_message.signature.hex()


def mint_certificate_custodial(user_acct,course_id: int, token_uri: str, signature: str):
    """
    Mint a certificate NFT from a user's custodial wallet.
    Auto gas estimation; exceptions caught if gas or funds are insufficient.
    """

    try:
        # Build transaction WITHOUT specifying gas or gasPrice
        txn = contract.functions.mintCertificate(
            course_id,
            token_uri,
            bytes.fromhex(signature)
        ).build_transaction({
            "from": user_acct.address,
            "nonce": w3.eth.get_transaction_count(user_acct.address),
            'gas': 800000,
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id
        })

        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(txn, private_key=user_acct.key.hex())

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        # Parse tokenId from CertificateMinted event
        events = contract.events.CertificateMinted().process_receipt(receipt)
        token_id = events[0]["args"]["tokenId"] if events else None

        return {"tx_hash": tx_hash.hex(), "token_id": token_id}

    except Exception as e:
        # This will catch errors like insufficient ETH, gas too low, etc.
        return {"error": str(e)}

def verify_minter_address(tokenId):
    minter = contract.functions.getOriginalMinter(tokenId).call()

    return minter

def certificate_ipfs(filepath):
    with open(filepath, "rb") as f:
        response = requests.post(url=pinata_url, headers=pinata_headers, files={"file": f},data={"network": "public"})
    result = response.json()
    return result['data']['cid']

def certificate_metadata(acct, course_title, course_id,image_ipfs):
    metadata = {
          "name": f"Cheta Certificate — {course_title}",
          "description": f"This certificate confirms successful completion of the {course_title} course on Cheta.",
          "image": f"ipfs://{image_ipfs}",
          "external_url": "https://cheta.xyz",
          "attributes": [
            { "trait_type": "Platform", "value": "Cheta" },
            { "trait_type": "Course ID", "value": f"{course_id}" },
            { "trait_type": "Recipient", "value": f'{acct}' },
            { "trait_type": "Issued On", "value": f"{datetime.now()}" },
            { "trait_type": "Certificate Type", "value": "Completion" },
            { "trait_type": "Transferable", "value": "Yes" }
          ]
        }

    # Convert metadata dict to JSON bytes
    metadata_json = json.dumps(metadata)


    files = {
        "file": ("metadata.json", metadata_json, "application/json")
    }

    response = requests.post(
        url=pinata_url,
        headers=pinata_headers,
        files=files,
        data={"network": "public"}
    )
    result = response.json()
    return result['data']['cid']

def check_subscription(user):
    # 1. If user has no subscription record
    try:
        sub = user.subscribe
    except Subscribe.DoesNotExist:

        return False  # means not allowed

    # 2. If subscription exists but not active
    if not sub.is_active:

        return False

    # 3. If subscription expired
    if sub.expires_at <= timezone.now():
        sub.is_active = False
        sub.save()

        return False

    return True

def connect_pkey(pkey):
    acct = Account.from_key(pkey)
    return acct