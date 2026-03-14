<template>
  <div class="page-shell help-shell">
    <div class="help-grid">
      <Card class="help-card">
        <template #content>
          <div class="help-list">
            <p><b>更新日期</b>：2026/03/14</p>
            <p><b>生效日期</b>：2026/03/14</p>

            <p>
              本隐私协议用于说明 FKUNIChat 在提供 API 转接与接口适配服务过程中，如何处理与您有关的信息。
              本服务定位为学习、研究、测试用途的技术工具，仅在提供转接功能所必需的范围内处理相关数据。
            </p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>数据处理说明</template>
        <template #content>
          <div class="help-list">
            <p>1.1 本应用默认将配置、Token、API Key 与运行状态保存在本地设备。</p>
            <p>1.2 USTChat Token 仅用于访问 USTChat 上游服务，不会主动上传到其他无关第三方服务。</p>
            <p>1.3 当您调用本地代理接口时，请求内容会被转发到 USTChat 上游模型服务，以完成相应的 AI 响应处理。</p>
            <p>1.4 本服务仅提供 API 转接与接口适配能力，不参与上游模型训练、微调、推理逻辑控制或内容生成。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>本地数据</template>
        <template #content>
          <div class="help-list">
            <p>2.1 本地保存的数据可能包括主题设置、监听地址、USTChat Token、本地 API Key 和调用次数统计。</p>
            <p>2.2 删除应用、清理本地存储或重置运行环境后，上述本地数据可能被移除。</p>
            <p>2.3 请您自行妥善保管本地设备、浏览器存储、配置文件及相关访问凭证，并自行承担因设备丢失、配置泄露或保管不当带来的风险。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>我们处理的信息</template>
        <template #content>
          <div class="help-list">
            <p>3.1 为实现 API 转接功能，本服务可能处理您提交的请求内容、调用参数、上下文信息及其他完成请求所必需的数据。</p>
            <p>3.2 为返回处理结果，本服务可能接收并转发上游 AI 服务返回的文本、代码、图片、结构化数据或其他响应内容。</p>
            <p>3.3 为保障服务正常运行，本服务可能处理必要的技术日志信息，包括请求时间、状态码、错误信息、调用次数、基础设备信息、网络请求元数据等。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>信息使用目的</template>
        <template #content>
          <div class="help-list">
            <p>4.1 相关信息仅用于实现请求接收、接口转发、响应返回以及基础功能运行。</p>
            <p>4.2 相关信息也可能用于必要的稳定性维护、故障排查、性能优化、安全防护及滥用识别。</p>
            <p>4.3 除完成 API 转接、保障安全稳定运行、履行法律义务所必需外，开发者不会主动将您的数据用于与本服务无关的用途。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>网络与访问风险</template>
        <template #content>
          <div class="help-list">
            <p>5.1 若您将服务监听地址设置为 <code>0.0.0.0</code>，同一网络中的其他设备可能访问您的本地服务。</p>
            <p>5.2 如您将本地代理暴露至公网、共享网络、校园网或其他不受信任环境，可能导致未授权访问、配置泄露或接口滥用等风险。</p>
            <p>5.3 请根据实际需要谨慎配置监听地址、端口、访问控制和本地 API Key，并避免在不安全网络环境中直接暴露服务。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>数据保留与安全</template>
        <template #content>
          <div class="help-list">
            <p>6.1 本服务仅在实现本协议所述目的所需的最短合理期限内保留必要信息。</p>
            <p>6.2 对于请求内容和响应内容，开发者将尽量减少留存；如为排查故障、安全审计、防止滥用或满足法律要求确有必要留存，将仅在必要范围和必要期限内处理。</p>
            <p>6.3 开发者将采取合理的技术和管理措施保护信息安全，包括但不限于访问控制、日志管理、最小权限和基础传输保护。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>用户注意事项</template>
        <template #content>
          <div class="help-list">
            <p>7.1 您不应通过本服务提交任何依法禁止传输、未经授权披露或明显超出学习测试必要范围的敏感信息、商业秘密、国家秘密或其他高风险数据。</p>
            <p>7.2 您应自行判断是否在本地环境中保存 USTChat Token、本地 API Key 或其他访问凭证，并自行承担相关配置风险。</p>
            <p>7.3 请勿将返回内容用于违反适用规则、第三方条款或法律法规的用途。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>第三方规则说明</template>
        <template #content>
          <div class="help-list">
            <p>8.1 本服务所转接的上游服务可能具有独立的服务条款、隐私政策、使用规范或数据处理规则，您在使用相应功能时，还应同时遵守该等规则。</p>
            <p>8.2 本服务中对 USTChat 或其他第三方名称的引用，仅用于说明接口来源、兼容对象或技术用途，不代表授权、许可、合作或官方关系。</p>
            <p>8.3 与上游服务相关的数据处理行为，还可能受到该上游服务自身规则约束，您应自行查阅并确认。</p>
            <p>
              USTChat 官方使用条款：
              <a href="https://chat.ustc.edu.cn/ustchat/policies/ustchat-terms-of-use.html" target="_blank"
                rel="noopener noreferrer">
                https://chat.ustc.edu.cn/ustchat/policies/ustchat-terms-of-use.html
              </a>
            </p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>协议更新</template>
        <template #content>
          <div class="help-list">
            <p>9.1 开发者有权根据法律法规变化、技术方案调整、上游服务变化或业务实际情况对本隐私协议进行更新。</p>
            <p>9.2 更新后的文本发布后生效；您在更新后继续使用本服务的，视为您已知悉并接受更新内容。</p>
            <p>9.3 如您不同意更新后的内容，应停止继续使用本服务。</p>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup>
import Card from "primevue/card";
</script>