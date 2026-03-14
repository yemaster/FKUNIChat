<template>
  <div class="page-shell help-shell">
    <div class="help-grid">
      <Card class="help-card">
        <template #content>
          <div class="help-list">
            <p><b>更新日期</b>：2026/03/14</p>
            <p><b>生效日期</b>：2026/03/14</p>

            <p>
              本服务条款适用于由开发者提供的 FKUNIChat API 转接与接口适配服务。请您在使用前仔细阅读并理解本条款。
              您通过访问、调用、部署、配置、测试或以其他方式使用本服务，即视为您已阅读、理解并同意接受本条款约束。
            </p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>服务性质</template>
        <template #content>
          <div class="help-list">
            <p>1.1 本服务系第三方独立开发的技术工具，仅提供请求转发、接口适配、协议封装、参数透传及相关技术接入能力。</p>
            <p>1.2 本服务不属于 USTChat 官方产品，亦未获得 USTChat 或其运营方的授权、合作背书或其他官方认可；除非另有明确书面说明，本服务与 USTChat 之间不存在代理、雇佣、联营、许可分销或其他关联关系。</p>
            <p>1.3 本服务仅供学习、研究、测试和技术交流用途，不面向商业运营承诺场景。您不得将本服务用于对外经营、收费转售、平台化分发或其他可能超出上游服务许可边界的用途。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>功能边界</template>
        <template #content>
          <div class="help-list">
            <p>2.1 本服务仅提供技术通道，不参与人工智能模型的训练、微调、推理、排序、审查或内容生成。</p>
            <p>2.2 您通过本服务获得的任何文本、代码、图片、表格、分析、建议或其他输出内容，均由上游 AI 服务基于您的输入自动生成。</p>
            <p>2.3 本服务本身不是该等内容的创作者、共同创作者、编辑者或发布者，对生成内容不主张基于创作行为产生的著作权或其他类似权利。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>使用要求</template>
        <template #content>
          <div class="help-list">
            <p>3.1 您应以合法、正当、善意方式使用本服务，不得利用本服务从事违法违规、侵权、滥用接口、绕过限制或危害网络安全的行为。</p>
            <p>3.2 您不得将本服务作为规避上游服务访问控制、配额限制、身份限制、内容规则或其他合规要求的工具。</p>
            <p>3.3 您应自行妥善保管本地配置中的 Token、API Key 或其他访问凭证，并自行承担因泄露、误配或不当使用造成的后果。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>用户责任</template>
        <template #content>
          <div class="help-list">
            <p>4.1 您对提交至本服务的输入内容及基于该等输入获得的输出内容负责。</p>
            <p>4.2 您应确保输入内容具有合法来源，不侵犯任何第三方的知识产权、隐私权、个人信息权益、商业秘密或其他合法权益。</p>
            <p>4.3 您应自行判断、审查和核验 AI 生成内容的真实性、准确性、完整性、合法性和适用性，不得将其作为唯一依据。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>免责声明</template>
        <template #content>
          <div class="help-list">
            <p>5.1 本服务对上游 AI 服务生成内容的真实性、准确性、完整性、时效性、合法性、不侵权性或适合特定目的不作任何明示或默示保证。</p>
            <p>5.2 因用户依赖输出内容作出判断、决策、发布、传播、引用或其他使用行为所产生的风险和后果，由用户自行承担。</p>
            <p>5.3 因上游服务故障、接口变更、访问限制、账号限制、网络异常、不可抗力或其他非开发者可控原因导致的中断、异常或不可用，开发者不承担责任。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>知识产权与第三方标识</template>
        <template #content>
          <div class="help-list">
            <p>6.1 本项目自身的源代码、接口封装逻辑、文档说明、页面设计及其他原创内容，其知识产权归开发者所有；另有开源许可证约定的，从其约定。</p>
            <p>6.2 “USTChat”及其相关名称、商标、服务标识、域名、页面元素等权利归其各自权利人所有。</p>
            <p>6.3 本服务中对 USTChat 或其他第三方名称的引用，仅用于说明接口来源、兼容对象或技术用途，不代表授权、许可、合作或官方关系。</p>
          </div>
        </template>
      </Card>

      <Card class="help-card">
        <template #title>服务变更与终止</template>
        <template #content>
          <div class="help-list">
            <p>7.1 开发者有权根据技术情况、维护安排、风险控制、合规要求或上游服务调整，对本服务进行更新、修改、限制、中止或终止。</p>
            <p>7.2 如发现存在违法违规、滥用、侵权、绕过限制、危害安全或其他不当使用情形，开发者有权拒绝继续提供服务。</p>
            <p>7.3 您在本条款更新后继续使用本服务的，视为您已接受更新后的条款内容。</p>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup>
import Card from "primevue/card";
</script>