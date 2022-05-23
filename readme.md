# cdn-backup-origin 帮助文档

<p align="center" class="flex justify-center">
    <a href="https://www.serverless-devs.com" class="ml-1">
    <img src="http://editor.devsapp.cn/icon?package=cdn-backup-origin&type=packageType">
  </a>
  <a href="http://www.devsapp.cn/details.html?name=cdn-backup-origin" class="ml-1">
    <img src="http://editor.devsapp.cn/icon?package=cdn-backup-origin&type=packageVersion">
  </a>
  <a href="http://www.devsapp.cn/details.html?name=cdn-backup-origin" class="ml-1">
    <img src="http://editor.devsapp.cn/icon?package=cdn-backup-origin&type=packageDownload">
  </a>
</p>

<description>

通过函数计算来实现抓取 CDN 源站信息并备份到备源站点的任务

</description>

<table>

## 前期准备
| 服务/业务 | 函数计算           |
| --------- | ------------------ |
| 权限/策略 | AliyunFCFullAccess |

</table>

<codepre id="codepre">

</codepre>

<deploy>

## 部署 & 体验

<appcenter>

- :fire: 通过 [Serverless 应用中心](https://fcnext.console.aliyun.com/applications/create?template=cdn-backup-origin) ，
[![Deploy with Severless Devs](https://img.alicdn.com/imgextra/i1/O1CN01w5RFbX1v45s8TIXPz_!!6000000006118-55-tps-95-28.svg)](https://fcnext.console.aliyun.com/applications/create?template=cdn-backup-origin)  该应用。 

</appcenter>

- 通过 [Serverless Devs Cli](https://www.serverless-devs.com/serverless-devs/install) 进行部署：
    - [安装 Serverless Devs Cli 开发者工具](https://www.serverless-devs.com/serverless-devs/install) ，并进行[授权信息配置](https://www.serverless-devs.com/fc/config) ；
    - 初始化项目：`s init cdn-backup-origin -d cdn-backup-origin`   
    - 进入项目，并进行项目部署：`cd cdn-backup-origin && s deploy -y`

</deploy>

<appdetail id="flushContent">

# 应用详情

通过该项目，可以抓取 CDN 源站信息并存储到备份站点上，还可以设置 CDN 加速节点进行预热
![alt](https://img.alicdn.com/imgextra/i1/O1CN01copy2j1n5uX8UVRGh_!!6000000005039-2-tps-1474-938.png)

## 初始化参数
| 参数名称       | 参数类型 | 是否必填 | 例子                                               | 参数含义                                                                                               |
| -------------- | -------- | -------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| serviceName    | String   | 选填     | cdn-backup-origin                                  | 函数服务名称名                                                                                         |
| functionName   | String   | 选填     | cdn-backup-origin                                  | 函数名称                                                                                               |
| roleArn        | String   | 必填     | 'acs:ram::123456:role/aliyuncdnserverlessdevsrole' | 函数执行角色                                                                                           |
| origin         | String   | 必填     | http://www.peersafe.cn/index.html                  | 源站地址                                                                                               |
| backupOrigin   | String   | 必填     | cdn-backup-bucket.oss-cn-beijing.aliyuncs.com      | 备源地址，仅支持OSS Bucket域名                                                                         |
| warmupDomain   | String   | 选填     | cdn-backup-bucket.oss-cn-beijing.aliyuncs.com      | 预热 CDN 域名                                                                                          |
| cronExpression | String   | 必填     | '@every 60m'                                       | 定时触发时间，参考 [函数计算](https://help.aliyun.com/document_detail/171746.html#section-gbz-k3r-vum) |
| warmupDomain   | String   | 选填     | warmup.com                                         | [CDN 预热域名](https://help.aliyun.com/document_detail/91161.html)                                     |
| enable         | Boolean  | 选填     | true                                               | 是否启用任务，默认值true。关闭后函数不再定时执行，不会再产生费用                                       |

## 执行效果
函数计算控制台查看任务历史
![alt](https://img.alicdn.com/imgextra/i3/O1CN01wGP6U61tHG2QPbp79_!!6000000005876-0-tps-3328-1442.jpg)
OSS控制台查看文件目录
![alt](https://img.alicdn.com/imgextra/i1/O1CN01a7rmwh1X7FqP5a1Qi_!!6000000002876-0-tps-3286-1602.jpg)
</appdetail>

<devgroup>

## 开发者社区

您如果有关于错误的反馈或者未来的期待，您可以在 [Serverless Devs repo Issues](https://github.com/serverless-devs/serverless-devs/issues) 中进行反馈和交流。如果您想要加入我们的讨论组或者了解 FC 组件的最新动态，您可以通过以下渠道进行：

<p align="center">

| <img src="https://serverless-article-picture.oss-cn-hangzhou.aliyuncs.com/1635407298906_20211028074819117230.png" width="130px" > | <img src="https://serverless-article-picture.oss-cn-hangzhou.aliyuncs.com/1635407044136_20211028074404326599.png" width="130px" > | <img src="https://serverless-article-picture.oss-cn-hangzhou.aliyuncs.com/1635407252200_20211028074732517533.png" width="130px" > |
| --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| <center>微信公众号：`serverless`</center>                                                                                         | <center>微信小助手：`xiaojiangwh`</center>                                                                                        | <center>钉钉交流群：`33947367`</center>                                                                                           |

</p>

</devgroup>