from html import escape as e
from pathlib import Path
import re
R=Path(__file__).resolve().parents[1]/'site'
U='https://www.breakingwalls.co'
A='/assets/img/'
B=A+'simulation/'
d={
'en':{
 'nav':('Studio','Games','Simulation','Robotics'), 'lead':('Independent studio · Montréal','Games and simulation. One studio.','We build games and interactive systems, from worlds you can play to environments and data you can train with.'),
 'doors': [('01 / Games','Games','Explore AWAY, Venus, Fold & Fly and the Breaking Walls portfolio.','Explore our games','home',A+'breakingwalls_gamemosaic.webp'),('02 / Simulation','Simulation','Real-time environments, AI workflows and motion capture for robotics.','Explore simulation','simulation/',B+'hero-bg.jpg')],
 'sim':('Simulation & AI','Interactive systems for training and research','Breaking Walls brings game development, real-time simulation and robotics data together to build and test responsive virtual environments.','Discuss a project','Explore robotics'),
 'areas':('Areas of work',[('Real-time simulation','Physics-based environments for training, virtual experimentation and digital twins.'),('Generative AI','AI orchestration, generative pipelines and custom tools for interactive content.'),('Robotics training','Motion capture and synthetic data workflows for robotics research and development.'),('Interactive experiences','Explore our games to see how we use simulation to create worlds that respond.')]),
 'platforms':('Our platforms',[('Ze1','A visual platform for building and orchestrating AI workflows.','https://www.ze1.io/'),('Sandscape','A platform for creating and editing playable games and worlds from prompts.','https://sandscape.app/')]),
 'projects':('Selected projects',[('AWAY: The Survival Series','Explore a living ecosystem through the eyes of a sugar glider.','away-the-survival-series'),('Robotics training lab','Explore the motion capture workflow and data formats.','simulation/robotics/'),('Game portfolio','Find Venus, Fold & Fly and our other projects.','home')]),
 'contact':('Work with us','For simulation, robotics and R&D partnerships:'),
 'robot':('Robotics training','Motion capture for robotics','We capture human movement and prepare synchronized motion data for robotics research and training.','Discuss your dataset','Back to simulation'),
 'pipeline':('From capture to dataset',[('Capture','Record full-body movement and hand poses for the tasks of interest.'),('Validation','Combine automated checks with human review, and recapture where needed.'),('Delivery','Prepare labeled, synchronized files and retarget data to the target skeleton as required.')]),
 'outputs':('Data and formats',[('Motion','Skeletal motion in BVH or FBX, hand poses, joint rotations and velocities.'),('Synchronized exports','Time-aligned camera streams, RGB, depth and point clouds depending on the capture setup.'),('Metadata','Task segments, timestamps, session tags and quality flags.')]),
 'uses':('Research applications','Imitation learning, reinforcement learning pretraining, sim-to-real research and industrial tasks such as assembly, tool use and object handling.'),
 'privacy':'Privacy policy','lang':'Language','skip':'Skip to content','back':'Return to the studio',
},
'fr':{
 'nav':('Studio','Jeux','Simulation','Robotique'), 'lead':('Studio indépendant · Montréal','Jeux et simulation. Un seul studio.','Nous créons des jeux et des systèmes interactifs, des mondes à explorer aux environnements et aux données qui servent à l’entraînement.'),
 'doors': [('01 / Jeux','Jeux','Découvrez AWAY, Venus, Fold & Fly et les autres jeux de Breaking Walls.','Découvrir nos jeux','home',A+'breakingwalls_gamemosaic.webp'),('02 / Simulation','Simulation','Environnements en temps réel, outils d’IA et capture de mouvement pour la robotique.','Découvrir la simulation','simulation/',B+'hero-bg.jpg')],
 'sim':('Simulation et IA','Des systèmes interactifs pour l’entraînement et la recherche','Breaking Walls réunit le jeu vidéo, la simulation en temps réel et les données robotiques pour créer et tester des environnements virtuels interactifs.','Discuter d’un projet','Découvrir la robotique'),
 'areas':('Champs d’activité',[('Simulation en temps réel','Environnements physiques pour l’entraînement, l’expérimentation virtuelle et les jumeaux numériques.'),('IA générative','Orchestration de l’IA, chaînes de génération et outils sur mesure pour les contenus interactifs.'),('Entraînement robotique','Capture de mouvement et données synthétiques pour la recherche et le développement en robotique.'),('Expériences interactives','Découvrez comment la simulation donne vie aux mondes de nos jeux.')]),
 'platforms':('Nos plateformes',[('Ze1','Une plateforme visuelle pour créer et orchestrer des flux de travail avec l’IA.','https://www.ze1.io/'),('Sandscape','Une plateforme pour créer et modifier des jeux et des mondes jouables à partir d’instructions.','https://sandscape.app/')]),
 'projects':('Projets en vedette',[('AWAY: The Survival Series','Explorez un écosystème vivant du point de vue d’un phalanger volant.','away-the-survival-series'),('Laboratoire de robotique','Découvrez le processus de capture et les formats de données.','simulation/robotics/'),('Portfolio de jeux','Retrouvez Venus, Fold & Fly et nos autres projets.','home')]),
 'contact':('Collaborer avec nous','Pour vos projets de simulation, de robotique ou de R-D :'),
 'robot':('Entraînement robotique','Capture de mouvement pour la robotique','Nous captons les mouvements humains et préparons des données synchronisées pour la recherche et l’entraînement en robotique.','Discuter de vos données','Retour à la simulation'),
 'pipeline':('De la capture aux données',[('Capture','Enregistrement des mouvements du corps et des mains pour les tâches ciblées.'),('Validation','Contrôles automatisés, vérification humaine et reprise des captures au besoin.'),('Livraison','Fichiers annotés et synchronisés, avec adaptation au squelette cible selon le projet.')]),
 'outputs':('Données et formats',[('Mouvement','Animation squelettique en BVH ou FBX, poses des mains, rotations articulaires et vitesses.'),('Exports synchronisés','Flux caméra alignés, données RVB, profondeur et nuages de points selon le dispositif de capture.'),('Métadonnées','Segments de tâches, horodatage, renseignements sur les sessions et indicateurs de qualité.')]),
 'uses':('Applications de recherche','Apprentissage par imitation, préentraînement par renforcement, transfert de la simulation au réel et tâches industrielles comme l’assemblage et la manipulation d’outils ou d’objets.'),
 'privacy':'Politique de confidentialité','lang':'Langue','skip':'Aller au contenu','back':'Revenir au studio',
}}
def loc(lang, path=''):
 return ('/fr/' if lang=='fr' else '/')+path
def out(lang,slug):
 return R/(lang if lang=='fr' else '')/slug/'index.html'
def write(lang,slug,body):
 f=out(lang,slug);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(body,encoding='utf-8')
def shell(lang,slug,title,desc,body):
 v=d[lang]; language='fr-CA' if lang=='fr' else 'en'
 nav=''.join(f'<a href="{loc(lang,p)}"{(" aria-current=page" if p==slug else "")}>{label}</a>' for label,p in zip(v['nav'],('','home','simulation/','simulation/robotics/')))
 langs=f'<a href="{loc("en",slug)}" lang="en" hreflang="en"{" aria-current=page" if lang=="en" else ""}>EN</a><a href="{loc("fr",slug)}" lang="fr" hreflang="fr"{" aria-current=page" if lang=="fr" else ""}>FR</a>'
 alt=''.join(f'<link rel="alternate" hreflang="{l}" href="{U+loc(m,slug)}">' for l,m in [('en','en'),('fr','fr'),('x-default','en')])
 return f'''<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Breaking Walls</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{U+loc(lang,slug)}">{alt}
<meta property="og:title" content="{e(title)} | Breaking Walls"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{U+loc(lang,slug)}"><meta property="og:type" content="website"><meta property="og:site_name" content="Breaking Walls">
<link rel="icon" href="/favicon.ico"><link rel="stylesheet" href="/assets/css/site.css"><link rel="stylesheet" href="/assets/css/studio.css">
</head>
<body class="bw-studio">
<a class="bw-skip" href="#content">{v['skip']}</a>
<header class="bw-top"><div class="bw-wrap bw-top-inner"><a class="bw-brand" href="{loc(lang)}"><img src="{A}bw_logo_white_cmyk_0.webp" alt="" width="44" height="44"><span>Breaking Walls</span></a><nav class="bw-nav" aria-label="{v['nav'][0]}">{nav}</nav><nav class="bw-lang" aria-label="{v['lang']}">{langs}</nav></div></header>
<main id="content" tabindex="-1">{body}</main>
<footer class="bw-footer"><div class="bw-wrap"><a href="{loc(lang)}">Breaking Walls</a><a href="{loc(lang,'privacy-policy')}">{v['privacy']}</a><span>Montréal, Canada</span></div></footer>
</body></html>
'''
def section(id,title,body):
 return f'<section class="bw-section" id="{id}"><div class="bw-wrap"><h2>{title}</h2>{body}</div></section>'
def cards(items,classes='bw-grid'):
 parts=[]
 for title,body,*rest in items:
  link='<a class="bw-link" href="'+e(rest[0],quote=True)+'">'+e(title)+' <span aria-hidden="true">↗</span></a>' if rest else ''
  parts.append(f'<article class="bw-card"><h3>{title}</h3><p>{body}</p>{link}</article>')
 return '<div class="'+classes+'">'+''.join(parts)+'</div>'
def hero(info,image,link1,link2):
 label,title,desc,t1,t2=info
 return f'<div class="bw-hero"><img class="bw-hero-img" src="{image}" alt="" fetchpriority="high"><div class="bw-wrap bw-hero-copy"><p class="bw-kicker">{label}</p><h1>{title}</h1><p class="bw-intro">{desc}</p><div class="bw-actions"><a class="bw-btn" href="{link1}">{t1}</a><a class="bw-btn bw-outline" href="{link2}">{t2}</a></div></div></div>'
def apply():
 for lang,v in d.items():
  lead=v['lead']
  doors=''.join(f'<a class="bw-door" href="{loc(lang,route)}"><img src="{img}" alt="" width="900" height="520"><div class="bw-door-copy"><p class="bw-kicker">{label}</p><h2>{title}</h2><p>{desc}</p><span class="bw-door-link">{cta} <span aria-hidden="true">→</span></span></div></a>' for label,title,desc,cta,route,img in v['doors'])
  body=f'<div class="bw-wrap bw-mast"><p class="bw-kicker">{lead[0]}</p><h1>{lead[1]}</h1><p class="bw-intro">{lead[2]}</p><div class="bw-doors">{doors}</div></div>'
  write(lang,'',shell(lang,'',lead[1],lead[2],body))
  contactTitle,contactDesc=v['contact']
  contact=section('contact',contactTitle,f'<p>{contactDesc}</p><a class="bw-link" href="mailto:info@breakingwalls.ca">info@breakingwalls.ca</a>')
  areaTitle,areaItems=v['areas']
  areaItems=[*areaItems[:3],(*areaItems[3],loc(lang,'home'))]
  platTitle,platforms=v['platforms']; projTitle,projects=v['projects']
  simpage=hero(v['sim'],B+'hero-bg.jpg','#contact',loc(lang,'simulation/robotics/'))
  simpage+=section('verticals',areaTitle,cards(areaItems))
  simpage+=section('vision','Our approach' if lang=='en' else 'Notre approche',f'<p class="bw-intro">{v["sim"][2]}</p>')
  simpage+=section('capabilities','Capabilities' if lang=='en' else 'Expertises',cards(areaItems[:3]))
  simpage+=section('sandscape',platTitle,cards(platforms,'bw-grid bw-two'))
  simpage+=section('projects',projTitle,cards([(t,p,loc(lang,url)) for t,p,url in projects]))+section('games', v['nav'][1], f'<a class="bw-link" href="{loc(lang,"home")}">{v["doors"][0][3]}</a>')+contact
  # English simulation routes are supplied by the checked-in Vite bundle.
  if lang != 'en':
   write(lang,'simulation/',shell(lang,'simulation/',v['nav'][2],v['sim'][2],simpage))
  rob=hero(v['robot'],B+'robotics-hero.jpg','#contact',loc(lang,'simulation/'))
  rob+=section('pipeline',v['pipeline'][0],cards(v['pipeline'][1]))
  rob+=section('formats',v['outputs'][0],f'<img class="bw-inline-image" src="{B}robotics-mocap.jpg" alt="" loading="lazy" width="1344" height="768">'+cards(v['outputs'][1]))
  rob+=section('applications',v['uses'][0],f'<p class="bw-intro">{v["uses"][1]}</p>')+contact
  if lang != 'en':
   write(lang,'simulation/robotics/',shell(lang,'simulation/robotics/',v['nav'][3],v['robot'][2],rob))
  # Add direct cross-navigation without changing game URLs or page content.
  file=out(lang,'home');h=file.read_text()
  href=loc(lang,'simulation/')
  if f'href="{href}"' not in h:
   for target in ('hd-nav','hd-mobile'):
    pat=r'(<(?:nav|div)\b[^>]*class="'+target+r'"[^>]*>\s*<ul>)'
    h,n=re.subn(pat,lambda m:m[0]+f'<li><a href="{href}">Simulation</a></li>',h,count=1)
    assert n==1,(lang,target)
   file.write_text(h)
 file=R/'sitemap.xml';s=file.read_text()
 for slug in ('simulation/','simulation/robotics/'):
  en,fr=(U+loc(l,slug) for l in ('en','fr'))
  for url in (en,fr):
   if f'<loc>{url}</loc>' not in s:
    line=f'  <url><loc>{url}</loc><xhtml:link rel="alternate" hreflang="en" href="{en}"/><xhtml:link rel="alternate" hreflang="fr" href="{fr}"/></url>\n'
    s=s.replace('</urlset>',line+'</urlset>')
 file.write_text(s)

if __name__ == "__main__":
 apply()
