"""Control-contract tests without a running Home Assistant instance."""
import importlib.util
from pathlib import Path
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

path=Path(__file__).parents[1]/"custom_components/pet_feeder_local/api.py"
spec=importlib.util.spec_from_file_location("feeder_api",path)
api=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=api
spec.loader.exec_module(api)


class Response:
    def __init__(self,status=200,data=None,error=None):
        self.status=status; self.data=data; self.error=error
    async def __aenter__(self):
        if self.error: raise self.error
        return self
    async def __aexit__(self,*args): return False
    async def json(self): return self.data


class Session:
    def __init__(self,response): self.response=response; self.calls=[]
    def request(self,*args,**kwargs):
        self.calls.append((args,kwargs)); return self.response


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def client(self,response):
        session=Session(response)
        return api.FeederClient(session,"http://feeder.local:8080","test-token"),session

    async def test_feed_timeout_is_not_retried(self):
        client,session=self.client(Response(error=TimeoutError()))
        with self.assertRaises(api.FeedOutcomeUnknown):
            await client.async_feed(2,"operation-1")
        self.assertEqual(len(session.calls),1)
        self.assertEqual(session.calls[0][1]["json"],{"portions":2,"operation_id":"operation-1"})

    async def test_feed_requires_matching_acknowledgement(self):
        client,session=self.client(Response(data={"accepted":True,"operation_id":"wrong-id"}))
        with self.assertRaises(api.FeedOutcomeUnknown):
            await client.async_feed(1,"operation-1")
        self.assertEqual(len(session.calls),1)

    async def test_server_error_is_an_unknown_feeding_outcome(self):
        client,session=self.client(Response(status=500))
        with self.assertRaises(api.FeedOutcomeUnknown):
            await client.async_feed(1,"operation-1")
        self.assertEqual(len(session.calls),1)

    async def test_rejected_feeding_request_is_not_accepted(self):
        client,session=self.client(Response(status=422))
        with self.assertRaises(api.RequestRejected):
            await client.async_feed(1,"operation-1")
        self.assertEqual(len(session.calls),1)

    async def test_invalid_operation_id_never_reaches_network(self):
        client,session=self.client(Response())
        with self.assertRaises(ValueError):
            await client.async_feed(1,"../operation")
        self.assertEqual(session.calls,[])

    async def test_feeding_is_explicit(self):
        client,session=self.client(Response(data={"accepted":True,"operation_id":"operation-1"}))
        self.assertEqual(session.calls,[])
        self.assertEqual(await client.async_feed(1,"operation-1"),"operation-1")
        self.assertEqual(session.calls[0][0][0],"POST")

    async def test_invalid_portions_never_reach_network(self):
        client,session=self.client(Response())
        for value in [0,11,True,1.5]:
            with self.assertRaises(ValueError): await client.async_feed(value)
        self.assertEqual(session.calls,[])

    async def test_schedule_conflict_is_preserved(self):
        client,session=self.client(Response(status=409))
        with self.assertRaises(api.ScheduleConflict):
            await client.async_set_schedule((),"old-revision")
        self.assertEqual(len(session.calls),1)

    async def test_schedule_requires_matching_mcu_readback(self):
        meal=api.Meal(127,8,0,2,True)
        client,_=self.client(Response(data={"revision":"new","meals":[],"verified":True}))
        with self.assertRaises(api.ScheduleVerificationError):
            await client.async_set_schedule((meal,),"old")

    async def test_readback_keeps_disabled_meals(self):
        meal=api.Meal(62,19,30,1,False)
        result={"revision":"new","meals":[api.asdict(meal)],"verified":True}
        client,_=self.client(Response(data=result))
        self.assertEqual((await client.async_set_schedule((meal,),"old")).meals,(meal,))

    async def test_redirects_are_not_followed(self):
        client,session=self.client(Response(status=302))
        with self.assertRaises(api.FeederError): await client.async_get_info()
        self.assertFalse(session.calls[0][1]["allow_redirects"])

    async def test_clock_sends_explicit_local_fields(self):
        client,session=self.client(Response(data={"acknowledged":True}))
        await client.async_set_clock(datetime(2026,11,23,20,15,30,tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")))
        self.assertEqual(session.calls[0][1]["json"],
                         {"year":2026,"month":11,"day":23,"hour":20,"minute":15,"second":30})

    async def test_naive_clock_never_reaches_network(self):
        client,session=self.client(Response())
        with self.assertRaises(ValueError):
            await client.async_set_clock(datetime(2026,11,23,20,15,30))
        self.assertEqual(session.calls,[])

    def test_invalid_meal_fields(self):
        for values in [(128,8,0,1,True),(127,24,0,1,True),(127,8,60,1,True),(127,8,0,0,True),(127,8,0,1,1)]:
            with self.assertRaises(ValueError): api.Meal(*values)


if __name__=="__main__": unittest.main()
