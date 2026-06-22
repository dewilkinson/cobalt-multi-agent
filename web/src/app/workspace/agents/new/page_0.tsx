78 [55] INFO  CopRequest [(null)] - COP Response url and time:https://ec.razer.com/1/setting/put281
2026-05-22 15:36:45,480 [55] INFO  CopRequest [(null)] - CurrentUser.Id: RZR_0280b21b4922a4b190fa8e03e4ba
2026-05-22 15:36:45,480 [55] INFO  CopRequest [(null)] - web request: https://ec.razer.com/1/setting/put
2026-05-22 15:36:45,481 [55] WARN  SettingManager [(null)] - COP Exception performing async push.
Razer.ActionService.CopException: Error performing request: (503)
   at Razer.ActionService.CopRequest`1.Execute()
   at Razer.AccountManager.SettingManager.SetSettingServer(RzSetting setting)
   at Razer.AccountManager.SettingManager.AsynWorker(Object state)
2026-05-22 15:36:45,482 [55] INFO  SettingManager [(null)] - New settings added while processing async items; resuming worker
2026-05-22 15:36:45,482 [55] INFO  SettingManager [(null)] - StartAsyncManager
2026-05-22 15:37:15,500 [40] INFO  SettingManager [(null)] - Starting Async Worker
2026-05-22 15:37:15,502 [40] INFO  SettingManager [(null)] - AsyncWorker: Processing upload item Devices\770\Features\e1e19823-51bb-4493-9524-7bf2bd33c25f/8997620a-f08d-49bd-aaec-0c5b0e55bac2.xml
2026-05-22 15:37:15,503 [40] INFO  SettingManager [(null)] - GetSettingServer
2026-05-22 15:37:15,505 [40] DEBUG CopRequest [(null)] - COP-SEND: action=POST, url=https://ec.razer.com/1/setting/get, payload=
<COP>
  <User>
    <ID>RZR_0280b21b4922a4b190fa8e03e4ba</ID>
    <Token>ey****************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************Q</Token>
  </User>
  <Setting>
    <Name>8997620a-f08d-49bd-aaec-0c5b0e55bac2.xml</Name>
    <Path>Devices\770\Features\e1e19823-51bb-4493-9524-7bf2bd33c25f</Path>
    <Data></Data>
  </Setting>
  <Product>
    <Name>Emily3</Name>
    <Version></Version>
  </Product>
</COP>
2026-05-22 15:37:15,791 [40] INFO  CopRequest [(null)] - COP Response url and time:https://ec.razer.com/1/setting/get282
2026-05-22 15:37:15,792 [40] INFO  CopRequest [(null)] - CurrentUser.Id: RZR_0280b21b4922a4b190fa8e03e4ba
2026-05-22 15:37:15,793 [40] INFO  CopRequest [(null)] - web request: https://ec.razer.com/1/setting/get
2026-05-22 15:37:15,793 [40] ERROR SettingManager [(null)] - Exception in GetSettingServer
Razer.ActionService.CopException: Error performing request: (503)
   at Razer.AccountManager.SettingManager.GetSettingServer(String path, String name, Boolean download)
2026-05-22 15:37:15,802 [40] DEBUG CopRequest [(null)] - COP-SEND: action=POST, url=https://ec.razer.com/1/setting/put, payload=
<COP>
  <User>
    <ID>RZR_0280b21b4922a4b190fa8e03e4ba</ID>
    <Token>ey*****************************************************************************************************************************************************************************************************************************************A</Token>
  </User>
  <Setting>
    <Name>a8664fc4-37d2-4bb7-978f-5ad11d7383ef.xml</Name>
    <Path>Devices\770\Features\58641b9d-4432-4ea4-8ddb-6defd558909b</Path>
    <Data></Data>
  </Setting>
  <Product>
    <Name>Emily3</Name>
    <Version></Version>
  </Product>
</COP>
2026-05-22 20:22:13,248 [21] INFO  CopRequest [(null)] - COP Response url and time:https://ec.razer.com/1/setting/get265
2026-05-22 20:22:13,249 [21] INFO  CopRequest [(null)] - CurrentUser.Id: RZR_0280b21b4922a4b190fa8e03e4ba
2026-05-22 20:22:13,249 [21] INFO  CopRequest [(null)] - web request: https://ec.razer.com/1/setting/get
2026-05-22 20:22:13,250 [21] ERROR SettingManager [(null)] - Exception in GetSettingServer
Razer.ActionService.CopException: Error performing request: (503)
   at Razer.AccountManager.SettingManager.GetSettingServer(String path, String name, Boolean download)
2026-05-22 20:22:13,258 [21] DEBUG CopRequest [(null)] - COP-SEND: action=POST, url=https://ec.razer.com/1/setting/put, payload=
<COP>
  <User>
    <ID>RZR_0280b21b4922a4b190fa8e03e4ba</ID>
    <Token>ey****************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************A</Token>
  </User>
  <Setting>
    <Name>a8664fc4-37d2-4bb7-978f-5ad11d7383ef.xml</Name>
    <Path>Devices\770\Features\58641b9d-4432-4ea4-8ddb-6defd558909b</Path>
    <Data>PD*********************************************************************************************************************************************************************************************=</Data>
    <Encoding>1</Encoding>
  </Setting>
  <Product>
    <Name>Emily3</Name>
    <Version></Version>
  </Product>
</COP>
2026-05-22 20:22:13,527 [21] INFO  CopRequest [(null)] - COP Response url and time:https://ec.razer.com/1/setting/put266
2026-05-22 20:22:13,528 [21] INFO  CopRequest [(null)] - CurrentUser.Id: RZR_0280b21b4922a4b190fa8e03e4ba
2026-05-22 20:22:13,529 [21] INFO  CopRequest [(null)] - web request: https://ec.razer.com/1/setting/put
2026-05-22 20:22:13,529 [21] WARN  SettingManager [(null)] - COP Exception performing async push.
Razer.ActionService.CopException: Error performing request: (503)
   at Razer.ActionService.CopRequest`1.Execute()
   at Razer.AccountManager.SettingManager.SetSettingServer(RzSetting setting)
   at Razer.AccountManager.SettingManager.AsynWorker(Object state)
2026-05-22 20:22:13,530 [21] INFO  SettingManager [(null)] - AsyncWorker: Processing upload item Devices\770\Features\58641b9d-4432-4ea4-8ddb-6defd558909b/6c91bf99-f6dd-4314-9982-97997d1bbced.xml
2026-05-22 20:22:13,531 [21] INFO  SettingManager [(null)] - GetSettingServer
2026-05-22 20:22:13,531 [21] DEBUG CopRequest [(null)] - COP-SEND: action=POST, url=https://ec.razer.com/1/setting/get, payload=
<COP>
  <User>
    <ID>RZR_0280b21b4922a4b190fa8e03e4ba</ID>
    <Token>ey************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************