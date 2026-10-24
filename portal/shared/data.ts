import projects from "../projects.json";
export { projects };
export const project = projects.find((p) => p.id === __DOCS_PROJECT__);
export const logo = "/img/FIT2CLOUD 飞致云 文档中心-01.png";
export const illustration = "/img/【主题】飞致云文档中心.png";
export const appliances = [
  {
    name: "1Panel AI 一体机",
    isNew: true,
    website: "https://1panel.cn/ai-appliance.html",
    logo: "1panel-07-蓝色.png",
  },
  {
    name: "MaxKB AI 一体机",
    website: "https://maxkb.cn/appliance",
    logo: "MaxKB-03.png",
  },
  {
    name: "JumpServer 一体机",
    website: "https://jumpserver.org/hardware.html",
    logo: "JumpServer-辅助图形-绿色.png",
  },
  {
    name: "Zabbix 信创一体机",
    website: "https://www.fit2cloud.com/zabbix/index.html",
    logo: "zabbix.png",
  },
];
export const navLinks = [
  ["如何购买", "https://www.fit2cloud.com/purchase/index.html"],
  ["论坛", "https://bbs.fit2cloud.com/"],
  ["培训认证", "https://edu.fit2cloud.com/"],
  ["关于我们", "https://www.fit2cloud.com/about/index.html"],
];
export const footerColumns = [
  {
    title: "快速浏览",
    links: [
      ["飞致云开源社区", "https://community.fit2cloud.com/", "group"],
      ["培训认证中心", "https://edu.fit2cloud.com/", "certificate"],
      [
        "案例中心",
        "https://www.fit2cloud.com/customers/index.html",
        "portfolio",
      ],
      ["如何购买", "https://www.fit2cloud.com/purchase/index.html", "purchase"],
      ["官方应用商店", "https://apps.fit2cloud.com/", "store"],
    ],
  },
  {
    title: "联系我们",
    links: [
      ["support@fit2cloud.com", "mailto:support@fit2cloud.com", "email"],
      ["400-052-0755", "tel:400-052-0755", "phone"],
      ["客户支持门户", "https://support.fit2cloud.com/", "headset"],
      ["产品预约演示", "https://jsj.top/f/UFPJsq", "demo"],
      ["申请成为合作伙伴", "https://jsj.top/f/vKGHRP", "document"],
    ],
  },
  {
    title: "资料下载",
    links: [
      [
        "1Panel 产品资料下载",
        "https://fit2cloud.com/1panel/download/introduce-1panel_2026.pdf",
        "document",
      ],
      [
        "JumpServer 产品资料下载",
        "https://fit2cloud.com/jumpserver/documents/introduce-jumpserver_2026.pdf",
        "document",
      ],
      [
        "MaxKB 产品资料下载",
        "https://fit2cloud.com/maxkb/download/introduce-maxkb_2026.pdf",
        "document",
      ],
      [
        "DataEase 产品资料下载",
        "https://fit2cloud.com/dataease/download/introduce-dataease_2026.pdf",
        "document",
      ],
      [
        "Cordys 产品资料下载",
        "https://fit2cloud.com/cordys/download/introduce-cordys_2026.pdf",
        "document",
      ],
    ],
  },
];
