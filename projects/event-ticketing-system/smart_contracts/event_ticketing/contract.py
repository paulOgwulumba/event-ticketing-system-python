from algopy import *


class EventTicketing(ARC4Contract):
    asset_id: UInt64
    ticket_price: UInt64
    asset_created: bool
    num_of_tickets: UInt64

    # create application
    @arc4.abimethod(allow_actions=['NoOp'], create='require')
    def create_application(self, num_of_tickets: UInt64, ticket_price: UInt64) -> None:
        assert num_of_tickets > 0, 'Number of tickets must be greater than 0'
        self.ticket_price = ticket_price
        self.num_of_tickets = num_of_tickets
        self.asset_created = False
    
    # bootstrap ticket asset
    @arc4.abimethod
    def bootstrap_ticket_asset(self, mbr_pay: gtxn.PaymentTransaction) -> UInt64:
        assert Txn.sender == Global.creator_address
        assert not self.asset_created

        assert mbr_pay.receiver == Global.current_application_address
        assert mbr_pay.amount >= Global.min_balance + Global.asset_create_min_balance

        asset_id = (
            itxn.AssetConfig(
                decimals=0,
                total=self.num_of_tickets,
                default_frozen=False,
                freeze=Global.current_application_address,
            )
            .submit()
            .created_asset.id
        )

        self.asset_id = asset_id
        self.asset_created = True

        log(asset_id)


        return self.asset_id

    # change ticket price
    @arc4.abimethod
    def update_price(self, new_price: UInt64) -> None:
        assert Txn.sender == Global.creator_address
        self.ticket_price = new_price

    # View current price
    @arc4.abimethod
    def view_price(self) -> UInt64:
        return self.ticket_price
    
    # View asset id
    @arc4.abimethod
    def view_asset(self) -> UInt64:
        return self.asset_id

    # buy ticket
    @arc4.abimethod
    def buy(self, buyer_txn: gtxn.PaymentTransaction) -> None:
        assert buyer_txn.receiver == Global.current_application_address
        assert buyer_txn.amount == self.ticket_price, 'Wrong price provided'
        assert self.num_of_tickets > 0, 'No tickets left'
        assert self.asset_created, 'Asset not created'

        ticket_asset = Asset(self.asset_id)
        assert Txn.sender.is_opted_in(ticket_asset), 'Asset not opted in'
        assert ticket_asset.balance(buyer_txn.sender) == 0, 'Ticket already bought'

        itxn.AssetTransfer(
            xfer_asset=self.asset_id,
            asset_receiver=buyer_txn.sender,
            asset_amount=1,
            fee=0,
        ).submit()

        # itxn.AssetFreeze(
        #     freeze_asset=self.asset_id,
        #     freeze_account=buyer_txn.sender,
        #     fee=0,
        #     frozen=False,
        #     sender=Global.current_application_address,
        # ).submit()

        self.num_of_tickets = self.num_of_tickets - 1


    # delete the application
    @arc4.abimethod(allow_actions=['DeleteApplication'])
    def deleteApplication(self) -> None:
        assert Txn.sender == Global.creator_address

        itxn.AssetTransfer(
            xfer_asset=self.asset_id,
            asset_receiver=Global.creator_address,
            asset_amount=0,
            asset_close_to=Global.creator_address,
        ).submit()

        itxn.Payment(
            amount=0,
            close_remainder_to=Global.creator_address,
            receiver=Global.creator_address,
        ).submit()