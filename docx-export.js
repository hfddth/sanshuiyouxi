(function(global){
  'use strict';

  const enc=new TextEncoder();
  let crcTable;

  function xml(value=''){
    return String(value).replace(/[&<>"']/g,char=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'
    }[char]));
  }

  function text(value){
    if(value==null)return'';
    if(Array.isArray(value))return value.filter(Boolean).join('、');
    return String(value).trim();
  }

  function crc32(bytes){
    if(!crcTable){
      crcTable=Array.from({length:256},(_,n)=>{
        let c=n;
        for(let i=0;i<8;i++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;
        return c>>>0;
      });
    }
    let crc=0xffffffff;
    for(const byte of bytes)crc=crcTable[(crc^byte)&255]^(crc>>>8);
    return(crc^0xffffffff)>>>0;
  }

  function u16(value){const out=new Uint8Array(2);new DataView(out.buffer).setUint16(0,value,true);return out}
  function u32(value){const out=new Uint8Array(4);new DataView(out.buffer).setUint32(0,value>>>0,true);return out}
  function join(parts){const size=parts.reduce((sum,part)=>sum+part.length,0),out=new Uint8Array(size);let at=0;for(const part of parts){out.set(part,at);at+=part.length}return out}

  function dosDateTime(date=new Date()){
    const year=Math.max(1980,date.getFullYear());
    return{
      time:(date.getHours()<<11)|(date.getMinutes()<<5)|(date.getSeconds()>>1),
      date:((year-1980)<<9)|((date.getMonth()+1)<<5)|date.getDate()
    };
  }

  function createZip(entries){
    const local=[],central=[];let offset=0;const stamp=dosDateTime();
    for(const entry of entries){
      const name=enc.encode(entry.name),data=entry.data instanceof Uint8Array?entry.data:enc.encode(entry.data),crc=crc32(data);
      const header=join([u32(0x04034b50),u16(20),u16(0x0800),u16(0),u16(stamp.time),u16(stamp.date),u32(crc),u32(data.length),u32(data.length),u16(name.length),u16(0),name]);
      local.push(header,data);
      central.push(join([u32(0x02014b50),u16(20),u16(20),u16(0x0800),u16(0),u16(stamp.time),u16(stamp.date),u32(crc),u32(data.length),u32(data.length),u16(name.length),u16(0),u16(0),u16(0),u16(0),u32(0),u32(offset),name]));
      offset+=header.length+data.length;
    }
    const centralData=join(central);
    const end=join([u32(0x06054b50),u16(0),u16(0),u16(entries.length),u16(entries.length),u32(centralData.length),u32(offset),u16(0)]);
    return join([...local,centralData,end]);
  }

  function runs(value,options={}){
    const chunks=String(value??'').split(/\r?\n/),props=[];
    if(options.bold)props.push('<w:b/>');
    if(options.color)props.push(`<w:color w:val="${options.color}"/>`);
    if(options.size)props.push(`<w:sz w:val="${options.size}"/><w:szCs w:val="${options.size}"/>`);
    const rPr=props.length?`<w:rPr>${props.join('')}</w:rPr>`:'';
    return chunks.map((chunk,index)=>`${index?'<w:r><w:br/></w:r>':''}<w:r>${rPr}<w:t xml:space="preserve">${xml(chunk)}</w:t></w:r>`).join('');
  }

  function paragraph(value='',style='Normal',options={}){
    const pPr=[style?`<w:pStyle w:val="${style}"/>`:''];
    if(options.align)pPr.push(`<w:jc w:val="${options.align}"/>`);
    if(options.keepNext)pPr.push('<w:keepNext/>');
    if(options.pageBreak)pPr.push('<w:pageBreakBefore/>');
    if(options.indent)pPr.push(`<w:ind w:left="${options.indent}"/>`);
    return `<w:p><w:pPr>${pPr.join('')}</w:pPr>${runs(value,options)}</w:p>`;
  }

  function heading(value,level=1){return paragraph(value,`Heading${Math.min(3,Math.max(1,level))}`,{keepNext:true})}
  function body(value){return text(value)?paragraph(text(value)) : ''}
  function quote(value){return text(value)?paragraph(text(value),'QuoteCN') : ''}
  function bullet(value){return text(value)?paragraph(`• ${text(value)}`,'ListBullet') : ''}
  function numbered(value,index){return text(value)?paragraph(`${index}. ${text(value)}`,'ListNumber') : ''}
  function labeled(label,value){return text(value)?body(`${label}：${text(value)}`):''}

  function firstText(...values){
    for(const value of values){
      const result=text(value);
      if(result)return result;
    }
    return'';
  }

  function chineseNumber(n){
    const digits=['零','一','二','三','四','五','六','七','八','九'];
    if(n<10)return digits[n];
    if(n===10)return'十';
    if(n<20)return`十${digits[n%10]}`;
    if(n<100)return`${digits[Math.floor(n/10)]}十${n%10?digits[n%10]:''}`;
    return String(n);
  }

  function findSpace(script,node){return(script.spaces||[]).find(space=>String(space.space_id)===String(node.space_id))||{}}

  function nodeSection(script,node,index){
    const space=findSpace(script,node),task=node.task||{},scene=node.scene||{},interaction=node.interaction||{},parts=[];
    parts.push(heading(`第${chineseNumber(index+1)}章｜${text(node.title)||`剧情节点 ${index+1}`}`,1));
    if(text(space.name)||text(space.description)){
      parts.push(heading('空间',2));
      parts.push(body([text(space.space_id),text(space.name),text(space.type)].filter(Boolean).join('｜')));
      parts.push(body(space.description));
    }
    if(text(node.opening_narration)){
      parts.push(heading(index===0?'剧情开场':'前旁白',2),quote(node.opening_narration));
    }
    if(text(scene.description)||text(scene.plot)){
      parts.push(heading('场景与剧情',2),labeled('场景',scene.description),labeled('剧情',scene.plot));
    }
    if(text(task.title)||text(task.objective)){
      parts.push(heading('任务目标',2),body(task.title),body(task.objective));
    }
    if((task.player_actions||[]).length){
      parts.push(heading('玩家行动',2),...(task.player_actions||[]).map(bullet));
    }
    if(text(task.completion_condition))parts.push(labeled('完成条件',task.completion_condition));
    if(text(interaction.description)||text(interaction.type)){
      parts.push(heading('互动',2),labeled('互动方式',interaction.type),body(interaction.description));
    }
    if((node.clues||[]).length){
      parts.push(heading('获得线索',2));
      for(const clue of node.clues){
        parts.push(body([text(clue.clue_id),text(clue.name)].filter(Boolean).join('｜')),quote(clue.content),labeled('来源',clue.source));
      }
    }
    if((node.culture||[]).length){
      parts.push(heading('文化依据',2));
      for(const item of node.culture){
        parts.push(body(item.name),body(item.description),labeled('来源',item.source),body(item.integration||item.plot_role||item.task_role));
      }
    }
    if((node.rewards||[]).length){
      parts.push(heading('获得奖励',2));
      for(const reward of node.rewards)parts.push(body([text(reward.name),text(reward.description)].filter(Boolean).join('：')));
    }
    if(text(node.closing_narration))parts.push(heading('后旁白',2),quote(node.closing_narration));
    return parts.filter(Boolean).join('');
  }

  function npcSection(script,sectionNumber){
    const npcs=script.npcs||[];
    if(!npcs.length)return'';
    const parts=[heading(`${chineseNumber(sectionNumber)}、人物角色`,1)];
    for(const npc of npcs){
      parts.push(heading(text(npc.name)||'剧情人物',2));
      parts.push(labeled('角色定位',npc.role||npc.function));
      parts.push(labeled('出场方式',npc.appearance_mode==='online'?'数字人':npc.appearance_mode==='offline'?'线下 NPC':npc.appearance_mode==='both'?'线上与线下':'剧情互动'));
      parts.push(labeled('性格',npc.personality));
      parts.push(labeled('背景',npc.background));
      parts.push(labeled('形象',npc.appearance));
      parts.push(labeled('关联空间',npc.space_ids));
      parts.push(labeled('关联节点',npc.plot_node_ids));
    }
    return parts.filter(Boolean).join('');
  }

  function flowSection(script,sectionNumber){
    const nodes=script.plot_nodes||[];
    if(!nodes.length)return'';
    const parts=[heading(`${chineseNumber(sectionNumber)}、剧本完整流程概览`,1)];
    nodes.forEach((node,index)=>{
      const space=findSpace(script,node),task=node.task||{},reward=(node.rewards||[])[0]||{};
      const summary=[text(node.node_id)||`N${String(index+1).padStart(2,'0')}`,text(node.title),text(space.name),text(task.title||task.objective),text(reward.name)].filter(Boolean).join(' → ');
      parts.push(numbered(summary,index+1));
    });
    return parts.join('');
  }

  function introductionSection(script){
    const project=script.project||{},ip=script.ip||{},world=script.world||{},story=script.story||{},nodes=script.plot_nodes||[],firstNode=nodes[0]||{},lastNode=nodes[nodes.length-1]||{},firstScene=firstNode.scene||{},firstTask=firstNode.task||{},lastTask=lastNode.task||{},parts=[];
    const synopsis=firstText(story.synopsis,project.synopsis,project.summary,firstScene.plot);
    const background=firstText(story.background,project.background,world.time_setting);
    const event=firstText(story.event,project.event,[text(firstNode.opening_narration),text(firstScene.plot)].filter(Boolean).join(' '));
    const intervention=firstText(story.player_intervention,project.player_intervention,firstTask.objective);
    const playerGoal=firstText(story.player_goal,world.player_goal,project.player_goal,lastTask.objective);
    const worldSetting=firstText(world.time_setting,project.worldview);
    const worldRules=firstText(world.world_rules,project.world_rules);
    const coreConflict=firstText(story.core_conflict,world.core_conflict,project.core_conflict);
    const finalGoal=firstText(world.final_goal,story.final_goal,project.final_goal,lastTask.completion_condition);
    const cultureRelation=firstText(world.culture_relation,story.culture_relation,project.culture_relation);

    parts.push(heading('二、故事简介',1));
    if(synopsis)parts.push(heading('故事梗概',2),body(synopsis));
    if(background)parts.push(heading('背景设定',2),body(background));
    if(event)parts.push(heading('事件起因',2),body(event));
    if(intervention)parts.push(heading('玩家介入',2),body(intervention));
    if(playerGoal)parts.push(heading('玩家目标',2),body(playerGoal));
    if(text(story.conflict_escalation))parts.push(heading('冲突升级',2),body(story.conflict_escalation));
    if(text(story.info_reveal))parts.push(heading('真相揭示',2),body(story.info_reveal));
    if(text(story.climax))parts.push(heading('剧情高潮',2),body(story.climax));
    if(text(story.ending))parts.push(heading('故事结局',2),body(story.ending));

    const ipItems=[
      ['IP 名称',ip.name],['核心概念',ip.concept],['项目定位',ip.positioning],['核心卖点',ip.selling_point],
      ['目标客群',ip.target_audience],['情绪价值',ip.emotional_value],['视觉风格',ip.visual_style]
    ].filter(([,value])=>text(value));
    if(ipItems.length){
      parts.push(heading('三、IP定位',1));
      for(const [label,value] of ipItems)parts.push(labeled(label,value));
    }

    const worldItems=[
      ['时空背景',worldSetting],['世界规则',worldRules],['核心冲突',coreConflict],
      ['玩家身份',firstText(world.player_identity,project.player_identity,project.player_role,project.identity)],
      ['最终目标',finalGoal],['文化与剧情关系',cultureRelation]
    ].filter(([,value])=>text(value));
    if(worldItems.length){
      parts.push(heading(`${ipItems.length?'四':'三'}、世界观与体验目标`,1));
      for(const [label,value] of worldItems)parts.push(labeled(label,value));
    }
    return{xml:parts.filter(Boolean).join(''),sectionCount:2+(ipItems.length?1:0)+(worldItems.length?1:0)};
  }

  function buildDocument(script){
    const project=script.project||{},name=text(project.name)||'未命名剧本',location=text(project.location)||text(project.scenic),type=text(project.type)||'沉浸式剧本游',players=text(project.players)||'建议人数待定',duration=text(project.duration)||'建议时长待定',identity=text(project.player_identity||project.player_role||project.identity)||'故事参与者',parts=[];
    parts.push(paragraph(`《${name.replace(/^《|》$/g,'')}》`,'Title',{align:'center'}));
    parts.push(paragraph(''),paragraph(''));
    parts.push(paragraph([location,type].filter(Boolean).join(' · '),'CoverMeta',{align:'center'}));
    parts.push(paragraph(''),paragraph(''));
    parts.push(paragraph(`故事地点：${location}`,'CoverMeta',{align:'center'}));
    parts.push(paragraph(`建议人数：${players}`,'CoverMeta',{align:'center'}));
    parts.push(paragraph(`建议时长：${duration}`,'CoverMeta',{align:'center'}));
    parts.push(paragraph(`玩家身份：${identity}`,'CoverMeta',{align:'center'}));
    parts.push(paragraph(''));
    parts.push(paragraph('一、剧本基本信息','Heading1',{keepNext:true,pageBreak:true}));
    parts.push(labeled('剧本名称',`《${name.replace(/^《|》$/g,'')}》`));
    parts.push(labeled('故事类型',type),labeled('故事地点',location),labeled('建议人数',players),labeled('建议时长',duration),labeled('玩家身份',identity));
    const introduction=introductionSection(script);
    parts.push(introduction.xml);
    (script.plot_nodes||[]).forEach((node,index)=>parts.push(nodeSection(script,node,index)));
    const base=introduction.sectionCount+1+(script.plot_nodes||[]).length;
    parts.push(npcSection(script,base),flowSection(script,base+((script.npcs||[]).length?1:0)));
    return{body:parts.filter(Boolean).join(''),title:name};
  }

  function stylesXml(){return`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:before="140" w:after="100" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="SimSun" w:hAnsi="SimSun" w:eastAsia="宋体"/><w:b/><w:color w:val="2F3A34"/><w:sz w:val="48"/><w:szCs w:val="48"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="CoverMeta"><w:name w:val="Cover Meta"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="100" w:line="336" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/></w:pPr><w:rPr><w:rFonts w:ascii="SimSun" w:hAnsi="SimSun" w:eastAsia="宋体"/><w:b/><w:color w:val="2F3A34"/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="140" w:after="100"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:b/><w:color w:val="40544C"/><w:sz w:val="27"/><w:szCs w:val="27"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="140" w:after="100"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:b/><w:color w:val="54665E"/><w:sz w:val="23"/><w:szCs w:val="23"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="QuoteCN"><w:name w:val="QuoteCN"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="397"/><w:spacing w:after="80" w:line="288" w:lineRule="auto"/></w:pPr><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:color w:val="4F5A55"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListNumber"><w:name w:val="List Number"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr></w:style>
</w:styles>`}

  function buildDocxBytes(script){
    const built=buildDocument(script),now=new Date().toISOString(),footerTitle=`《${built.title.replace(/^《|》$/g,'')}》`;
    const document=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>${built.body}<w:sectPr><w:footerReference w:type="default" r:id="rId1"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1247" w:right="1417" w:bottom="1247" w:left="1417" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>`;
    const footer=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="微软雅黑"/><w:color w:val="888888"/><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr><w:t>${xml(footerTitle)}</w:t></w:r></w:p></w:ftr>`;
    const entries=[
      {name:'[Content_Types].xml',data:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`},
      {name:'_rels/.rels',data:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>`},
      {name:'word/document.xml',data:document},
      {name:'word/styles.xml',data:stylesXml()},
      {name:'word/footer1.xml',data:footer},
      {name:'word/_rels/document.xml.rels',data:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`},
      {name:'docProps/core.xml',data:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${xml(built.title)}</dc:title><dc:creator>山水有戏</dc:creator><cp:lastModifiedBy>山水有戏</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">${now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">${now}</dcterms:modified></cp:coreProperties>`},
      {name:'docProps/app.xml',data:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>山水有戏</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop><Company></Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>1.0</AppVersion></Properties>`}
    ];
    return createZip(entries);
  }

  function safeFileName(value){return(text(value)||'未命名剧本').replace(/[\\/:*?"<>|]/g,'_').replace(/[. ]+$/g,'').slice(0,80)}

  function exportScript(script){
    if(!script||!script.project)throw new Error('没有可导出的剧本内容');
    const bytes=buildDocxBytes(script),blob=new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download=`${safeFileName(script.project.name)}_完整剧本.docx`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
  }

  global.ScriptDocxExporter={buildDocxBytes,exportScript,safeFileName};
})(typeof window!=='undefined'?window:globalThis);

