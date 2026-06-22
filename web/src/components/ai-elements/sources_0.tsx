************************************************************************************************************************************************************************************************************************************************************************************************************************************************************A</Token>
  </User>
  <Setting>
    <Name>8997620a-f08d-49bd-aaec-0c5b0e55bac2.xml</Name>
    <Path>Devices\770\Features\e1e19823-51bb-4493-9524-7bf2bd33c25f</Path>
    <Data>PD*****************************************************************************************************************************************************************************************************************************************************************************************************************+</Data>
    <Encoding>1</Encoding>
  </Setting>
  <Product>
    <Name>Emily3</Name>
    <Version></Version>
  </Product>
</COP>
2026-05-23 00:06:22,636 [13] INFO  CopRequest [(null)] - COP Response url and time:https://ec.razer.com/1/setting/put360
2026-05-23 00:06:22,637 [13] INFO  CopRequest [(null)] - CurrentUser.Id: RZR_0280b21b4922a4b190fa8e03e4ba
2026-05-23 00:06:22,638 [13] INFO  CopRequest [(null)] - web request: https://ec.razer.com/1/setting/put
2026-05-23 00:06:22,638 [13] WARN  SettingManager [(null)] - COP Exception performing async push.
Razer.ActionService.CopException: Error performing request: (503)
   at Razer.ActionService.CopRequest`1.Execute()
   at Razer.AccountManager.SettingManager.SetSettingServer(RzSetting setting)
   at Razer.AccountManager.SettingManager.AsynWorker(Object state)
2026-05-23 00:06:22,639 [13] INFO  SettingManager [(null)] - AsyncWorker: Processing upload item Devices\770\Features\58641b9d-4432-4ea4-8ddb-6defd558909b/03bec892-2c22-4990-8000-a8cfb1a4c