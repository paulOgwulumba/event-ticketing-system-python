import algokit_utils
import algokit_utils.logic_error
import pytest
from algokit_utils import get_localnet_default_account
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from algokit_utils.beta.algorand_client import AlgorandClient, PayParams, AssetOptInParams
from algokit_utils.beta.account_manager import AddressAndSigner
from algosdk.atomic_transaction_composer import TransactionWithSigner
import algosdk

from smart_contracts.artifacts.event_ticketing.client import EventTicketingClient

PRICE = 1000
NUM_OF_TICKETS = 10

@pytest.fixture(scope='session')
def algorand() -> AlgorandClient:
    """Get an AlgorandClient to use throughout the tests."""
    return AlgorandClient.default_local_net()

@pytest.fixture(scope='session')
def dispenser(algorand: AlgorandClient) -> AddressAndSigner:
    """Get the dispenser to fund test addresses"""
    return algorand.account.dispenser()

@pytest.fixture(scope='session')
def creator(algorand: AlgorandClient, dispenser: AddressAndSigner) -> AddressAndSigner:
    account = algorand.account.random()
    algorand.send.payment(PayParams(
        sender=dispenser.address,
        receiver=account.address,
        amount=10_000_000,
        signer=dispenser.signer,
    ))

    return account

@pytest.fixture(scope='session')
def buyer(algorand: AlgorandClient, dispenser: AddressAndSigner) -> AddressAndSigner:
    account = algorand.account.random()
    algorand.send.payment(PayParams(
        sender=dispenser.address,
        receiver=account.address,
        amount=10_000_000,
        signer=dispenser.signer,
    ))

    return account

@pytest.fixture(scope='session')
def event_ticketing_client(
    algorand: AlgorandClient,
    creator: AddressAndSigner,
) -> EventTicketingClient:
    client = EventTicketingClient(
        algod_client=algorand.client.algod,
        sender=creator.address,
        signer=creator.signer,
    )
    
    client.create_create_application(
        num_of_tickets=NUM_OF_TICKETS,
        ticket_price=PRICE,
    )

    return client

@pytest.fixture(scope='session')
def asset_id(
    event_ticketing_client: EventTicketingClient,
    algorand: AlgorandClient,
    creator: AddressAndSigner,
) -> int:
    txn = algorand.transactions.payment(PayParams(
        sender=creator.address,
        receiver=event_ticketing_client.app_address,
        amount=200_000,
        extra_fee=1_000,
    ))

    result = event_ticketing_client.bootstrap_ticket_asset(
        mbr_pay=TransactionWithSigner(
            txn=txn,
            signer=creator.signer,
        )
    )

    asset_id = result.return_value

    return asset_id


def test_create_application(
    event_ticketing_client: EventTicketingClient,
) -> None:
    assert event_ticketing_client.app_id is not None
    pass

def test_bootstrap(
    event_ticketing_client: EventTicketingClient,
    algorand: AlgorandClient,
    asset_id: int,
) -> None:
    assert algorand.account.get_asset_information(
        event_ticketing_client.app_address, asset_id
    )['asset-holding']['amount'] == NUM_OF_TICKETS

def test_view_price(
    event_ticketing_client: EventTicketingClient,
) -> None:
    result = event_ticketing_client.view_price()

    assert result.return_value == PRICE

def test_view_asset(
    event_ticketing_client: EventTicketingClient,
    asset_id: int,
) -> None:
    result = event_ticketing_client.view_asset()

    assert result.return_value == asset_id

def test_buy(
    event_ticketing_client: EventTicketingClient,
    asset_id: int,
    buyer: AddressAndSigner,
    algorand: AlgorandClient,
) -> None:
    algorand.send.asset_opt_in(AssetOptInParams(
        asset_id=asset_id,
        sender=buyer.address,
        signer=buyer.signer,
    ))

    assert algorand.account.get_asset_information(
        buyer.address, asset_id
    )['asset-holding']['amount'] == 0

    payment_txn = algorand.transactions.payment(PayParams(
        signer=buyer.signer,
        sender=buyer.address,
        amount=PRICE,
        receiver=event_ticketing_client.app_address,
        extra_fee=1_000,
    ))

    result = event_ticketing_client.buy(
        buyer_txn=TransactionWithSigner(
            txn=payment_txn,
            signer=buyer.signer,
        ),
        transaction_parameters=algokit_utils.TransactionParameters(
            foreign_assets=[asset_id],
            sender=buyer.address,
            signer=buyer.signer,
        )
    )

    assert result.confirmed_round

    assert algorand.account.get_asset_information(
        buyer.address, asset_id
    )['asset-holding']['amount'] == 1

def test_buy_negative(
    event_ticketing_client: EventTicketingClient,
    asset_id: int,
    buyer: AddressAndSigner,
    algorand: AlgorandClient,
) -> None:
    payment_txn = algorand.transactions.payment(PayParams(
        signer=buyer.signer,
        sender=buyer.address,
        amount=PRICE,
        receiver=event_ticketing_client.app_address,
        extra_fee=1_000,
    ))

    pytest.raises(
        expected_exception=algokit_utils.logic_error.LogicError,
        match=lambda: event_ticketing_client.buy(
            buyer_txn=TransactionWithSigner(
                txn=payment_txn,
                signer=buyer.signer,
            ),
            transaction_parameters=algokit_utils.TransactionParameters(
                foreign_assets=[asset_id],
                sender=buyer.address,
                signer=buyer.signer,
            )
        )
    )

def delete_application(
    event_ticketing_client: EventTicketingClient,
    asset_id: int,
    creator: AddressAndSigner,
    algorand: AlgorandClient,   
) -> None:
    algorand.send.asset_opt_in(AssetOptInParams(
        asset_id=asset_id,
        sender=creator.address,
        signer=creator.signer,
    ))

    result = event_ticketing_client.delete_delete_application(
        transaction_parameters=algokit_utils.TransactionParameters(
            foreign_assets=[asset_id],
        )
    )

    assert result.confirmed_round

    assert algorand.account.get_asset_information(
        creator.address, asset_id
    )['asset-holding']['amount'] == 9



