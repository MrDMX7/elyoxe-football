/* Who Tifo is, for search engines (owner 2026-10-09): the home page's WebSite + Organization JSON-LD. Search results then
   show «تيفو» and its logo above every page instead of a guessed host name, and Tifo is not taken for the English «Tifo
   Football». The publisher is Elyoxe with its social accounts (memory: project_elyoxe_x_profile). tests/test_site_identity.py */
"use strict";
function siteLd(site){
  const org = { "@type":"Organization", "@id":"https://elyoxe.com/#org", name:"Elyoxe", url:"https://elyoxe.com/",
    logo:{ "@type":"ImageObject", url:`${site}/icons/apple-touch-icon.png`, width:180, height:180 },
    sameAs:["https://x.com/Elyoxe", "https://www.instagram.com/elyo.xe/", "https://www.tiktok.com/@elyoxe"] };
  const web = { "@type":"WebSite", "@id":`${site}/#website`, name:"تيفو", alternateName:["Tifo", "تيفو كورة", "Tifo by Elyoxe"],
    url:`${site}/`, inLanguage:"ar", description:"نتائج مباريات اليوم مباشر لكل العرب: الدوريات العربية والعالمية، القنوات الناقلة والمعلقين، والأرقام.",
    publisher:{ "@id":org["@id"] } };
  return [Object.assign({ "@context":"https://schema.org" }, web), Object.assign({ "@context":"https://schema.org" }, org)];
}
module.exports = { siteLd };
