*******************************************+</Data>
    <Encoding>1</Encoding>
  </Setting>
  <Product>
    <Name>Emily3</Name>
    <Version></Version>
  </Product>
</COP>
2026-05-22 10:06:48,648 [18] INFO  CopRequest [(null)] - COP Response url and time:https://ec.razer.com/1/setting/put265
2026-05-22 10:06:48,649 [18] INFO  CopRequest [(null)] - CurrentUser.Id: RZR_0280b21b4922a4b190fa8e03e4ba
2026-05-22 10:06:48,649 [18] INFO  CopRequest [(null)] - web request: https://ec.razer.com/1/setting/put
2026-05-22 10:06:48,650 [18] WARN  SettingManager [(null)] - COP Exception performing async push.
Razer.ActionService.CopException: Error performing request: (503)
   at Razer.ActionService.CopRequest`1.Execute()
   at Razer.AccountManager.SettingManager.SetSettingServer(RzSetting setting)
   at Razer.AccountManager.SettingManager.AsynWorker(Object state)
2026-05-22 10:06:48,652 [18] INFO  SettingManager [(null)] - AsyncWorker: Processing upload item Devices\770\Features\58641b9d-4432-4ea4-8ddb-6defd558909b/03bec892-2c22-4990-8000-a8cfb1a4c25b.xml
2026-05-22 10:06:48,653 [18] INFO  SettingManager [(null)] - GetSettingServer
2026-05-22 10:06:48,654 [18] DEBUG CopRequest [(null)] - COP-SEND: action=POST, url=https://ec.razer.com/1/setting/get, payload=
<COP>
  <User>
    <ID>RZR_0280b21b4922a4b190fa8e03e4ba</ID>
    <Token>ey***************************************************************************************************************************************************************************************************************************************