import type { Translation } from "./types";

export const es: Translation = {
  common: {
    skipContent: "Saltar al contenido",
    nav: {
      home: "Inicio",
      services: "Servicios",
      coverage: "Cobertura",
      contact: "Contacto",
      apply: "Solicitar",
    },
    language: {
      next: "EN",
      aria: "Cambiar a inglés",
    },
    footer: {
      copyright: "© 2026 TrackFlow. Todos los derechos reservados.",
      updated: "Última actualización: abril de 2026",
      privacy: "Política de Privacidad",
      linkedin: "LinkedIn",
    },
  },
  home: {
    hero: {
      headlineLead: "Logistica que escala con tu",
      headlineHighlight: "e-commerce",
      subheading:
        "Gestión de almacén, entregas de última milla y logística inversa en Estados Unidos y España. Más de 15 años ayudando a marcas de moda, electrónica y cosmética a crecer sin preocuparse por las operaciones.",
      cta: "Solicitar información",
      imageAlt:
        "Área moderna de despacho de almacén con paquetes moviéndose desde almacenamiento hacia una furgoneta de reparto",
    },
    services: {
      title: "Nuestros Servicios",
      subtitle:
        "Soluciones logísticas integrales para marcas de e-commerce en Estados Unidos y España.",
      cards: [
        {
          title: "Gestión de Almacén",
          items: [
            "Almacenamiento, picking y packing",
            "Inventario en tiempo real",
            "Almacenes en Los Ángeles y Zaragoza",
          ],
        },
        {
          title: "Entregas de Última Milla",
          items: [
            "Red de transportistas certificados en ambos países",
            "Seguimiento unificado de envíos",
            "Gestión de incidencias y devoluciones",
          ],
        },
        {
          title: "Logística Inversa",
          items: [
            "Gestión completa de devoluciones",
            "Inspección y reacondicionamiento",
            "Integración con tu plataforma de ventas",
          ],
        },
      ],
    },
    coverage: {
      title: "Nuestra Cobertura",
      subtitle:
        "Infraestructura propia en dos mercados - el único operador logístico con almacenes en Estados Unidos y España.",
      warehouseLabel: "Almacén",
      coverageLabel: "Cobertura",
      carriersLabel: "Transportistas",
      regions: [
        {
          market: "Estados Unidos",
          city: "Los Ángeles, California",
          warehouse: "Los Ángeles - instalación principal",
          coverage: "Cobertura nacional en Estados Unidos",
          carriers: "UPS, FedEx, DHL",
        },
        {
          market: "España",
          city: "Zaragoza, Aragón",
          warehouse: "Zaragoza - instalación principal",
          coverage: "Cobertura peninsular e insular",
          carriers: "MRW, SEUR, DHL",
        },
      ],
    },
    benefits: {
      title: "Por Que TrackFlow",
      subtitle:
        "Fundada en 2009. Con la confianza de marcas líderes de e-commerce en dos continentes.",
      cards: [
        {
          title: "Operación Binacional",
          description:
            "El único operador con infraestructura propia en Estados Unidos y España",
        },
        {
          title: "+130 Profesionales",
          description: "Dedicados a tu logística en ambos países",
        },
        {
          title: "Tecnología Propia",
          description:
            "Visibilidad total de tu inventario con nuestra plataforma propietaria",
        },
        {
          title: "Especialización en E-commerce",
          description: "Marcas de moda, electrónica y cosmética confían en nosotros",
        },
      ],
    },
    faq: {
      title: "Preguntas Frecuentes",
      subtitle:
        "Respuestas a las preguntas más comunes sobre los servicios logísticos de TrackFlow.",
      items: [
        {
          question: "¿Qué es TrackFlow?",
          answer:
            "TrackFlow es un proveedor de logística de terceros fundado en 2009, especializado en gestión de almacenes, entregas de última milla y logística inversa para marcas de e-commerce en Estados Unidos y España. Operamos dos instalaciones - Los Ángeles, California y Zaragoza, España - con más de 130 profesionales de la logística.",
        },
        {
          question: "¿Qué mercados atiende TrackFlow?",
          answer:
            "TrackFlow opera en Estados Unidos y España. Nuestro almacén en Los Ángeles ofrece cobertura nacional en EE.UU. con UPS, FedEx y DHL. Nuestro almacén en Zaragoza cubre la península y las islas en España con MRW, SEUR y DHL.",
        },
        {
          question: "¿Qué volumen de envíos requiere TrackFlow?",
          answer:
            "TrackFlow está diseñado para empresas de e-commerce con 100 o más pedidos mensuales. Para marcas con un volumen inferior, nuestro modelo de 3PL integral puede no ser la opción más eficiente; se lo indicaremos directamente durante la consulta inicial.",
        },
        {
          question: "¿En qué categorías de producto se especializa TrackFlow?",
          answer:
            "TrackFlow se especializa en moda, electrónica y cosmética. Estas categorías requieren un manejo específico - control de temperatura, embalaje seguro y seguimiento preciso del inventario - que nuestras instalaciones están equipadas para proporcionar.",
        },
        {
          question: "¿Con qué rapidez responde TrackFlow a las solicitudes de información?",
          answer:
            "Nuestro equipo comercial revisa cada solicitud y responde en un plazo de 24 a 48 horas hábiles. A continuación, programamos una llamada de descubrimiento para entender su volumen, tipo de producto y necesidades operativas antes de proponer un acuerdo de servicio.",
        },
      ],
    },
    contact: {
      title: "Contáctenos",
      subtitle:
        "Nuestro equipo comercial está listo para ayudarte a escalar tus operaciones logísticas.",
      emailLabel: "Correo electrónico",
      losAngelesLabel: "Los Ángeles",
      zaragozaLabel: "Zaragoza",
      cta: "Solicitar informacion",
    },
  },
  application: {
    title: "Solicitar Información",
    subtitle:
      "Cuéntenos sobre su empresa y necesidades logísticas. Nuestro equipo comercial le contactará en 24-48 horas.",
    form: {
      fieldsets: {
        company: "Información de la Empresa",
        service: "Información del Servicio",
      },
      fields: {
        companyName: { label: "Nombre de la empresa", placeholder: "Acme Corp" },
        contactPerson: { label: "Persona de contacto", placeholder: "Ana García" },
        corporateEmail: {
          label: "Correo corporativo",
          placeholder: "nombre@empresa.com",
        },
        phone: {
          label: "Teléfono",
          placeholder: "+34 976 123 456",
          hint: "Incluya el código de país, ej. +34 976 123 456",
        },
        companyWebsite: {
          label: "Sitio web de la empresa",
          placeholder: "https://suempresa.com",
        },
        operatingCountry: {
          label: "País de operación principal",
          placeholder: "Seleccione un país",
        },
        productType: {
          label: "Tipo de producto",
          placeholder: "Seleccione tipo de producto",
        },
        monthlyVolume: {
          label: "Volumen mensual estimado de envíos",
          placeholder: "Seleccione rango de volumen",
        },
        services: { label: "Servicios de interés" },
        current3pl: { label: "¿Trabaja actualmente con otro operador 3PL?" },
        comments: {
          label: "Comentarios o necesidades específicas",
          placeholder:
            "Cuéntenos sobre sus necesidades específicas o cualquier pregunta...",
        },
        privacyPolicy: {
          text: "Acepto la",
          link: "política de privacidad",
        },
      },
      options: {
        countries: {
          us: "Estados Unidos",
          es: "España",
          both: "Ambos",
          other: "Otro",
        },
        products: {
          fashion: "Moda",
          electronics: "Electrónica",
          cosmetics: "Cosmética",
          food: "Alimentación",
          other: "Otro",
        },
        volumes: {
          "0-100": "0-100 envíos/mes",
          "101-500": "101-500 envíos/mes",
          "501-2000": "501-2.000 envíos/mes",
          "2000+": "2.000+ envíos/mes",
          "not-sure": "No estoy seguro",
        },
        services: {
          warehousing: "Almacenaje",
          "last-mile": "Última milla",
          "reverse-logistics": "Logística inversa",
        },
        current3pl: {
          yes: "Sí",
          no: "No",
          evaluating: "Evaluando opciones",
        },
      },
      lowVolumeWarning:
        "Para volúmenes inferiores a 100 envíos mensuales, nuestros servicios podrían no ser la solución más eficiente. ¿Está seguro de querer continuar?",
      remaining: "restantes",
      overLimit: "sobre el límite",
      requiredNote: "Campos obligatorios",
      submit: "Enviar solicitud",
      clear: "Limpiar formulario",
      optional: "(opcional)",
      success: {
        title: "¡Gracias por su interés en TrackFlow!",
        body:
          "Hemos recibido su solicitud. Nuestro equipo comercial revisará su información y se pondrá en contacto en las próximas 24-48 horas para concertar una llamada y conocer en detalle sus necesidades logísticas.",
        urgent: "Si tiene alguna consulta urgente, escríbanos directamente a",
      },
      errors: {
        companyName: "El nombre de la empresa debe tener al menos 2 caracteres",
        contactPerson:
          "Introduzca el nombre y apellido de la persona de contacto",
        corporateEmail:
          "Introduzca un correo corporativo válido (ejemplo: nombre@empresa.com)",
        phone:
          "El teléfono debe incluir el código de país (ejemplo: +34 976 123 456)",
        companyWebsite: "Si incluye sitio web, debe ser una URL válida",
        operatingCountry: "Seleccione el país de operación principal",
        productType: "Seleccione el tipo de producto que gestiona",
        monthlyVolume: "Seleccione el volumen mensual estimado",
        services: "Seleccione al menos un servicio de interes",
        current3pl:
          "Indique si trabaja actualmente con otro proveedor logístico",
        comments: "El comentario supera el límite de 500 caracteres",
        privacyPolicy: "Debe aceptar la política de privacidad para continuar",
      },
    },
  },
  privacy: {
    title: "Política de Privacidad",
    updated: "Última actualización: 24 de abril de 2026",
    sections: {
      about: "Sobre Este Sitio",
      aboutBody:
        "TrackFlow es un proyecto de portafolio desarrollado como parte de un programa de Ingeniería en IA en 4Geeks Academy. El escenario de la empresa, los servicios y los detalles operativos son realistas y representativos de una operación logística profesional, pero TrackFlow no es un negocio comercialmente activo.",
      data: "Información Enviada A Través Del Formulario",
      dataBody:
        "recopila el nombre de la empresa, nombre de contacto, correo electrónico, número de teléfono y requisitos logísticos. Dado que TrackFlow es un proyecto de portafolio:",
      dataItems: [
        "Los envíos del formulario no se procesan comercialmente.",
        "Ningún dato enviado se almacena en una base de datos de producción ni se comparte con terceros.",
        "El formulario existe para demostrar un flujo de captación de clientes potenciales completo y de calidad profesional.",
      ],
      cookies: "Cookies Y Almacenamiento Local",
      cookiesBody:
        "Este sitio utiliza localStorage del navegador para recordar su preferencia de idioma entre visitas. No se establecen cookies de seguimiento, cookies de análisis ni cookies de terceros.",
      hosting: "Alojamiento",
      hostingBody:
        "Este sitio está alojado en Vercel. Vercel puede recopilar registros de servidor estándar como dirección IP, tipo de navegador y páginas visitadas como parte de la infraestructura de alojamiento normal.",
      contact: "Contacto",
      contactBody:
        "Las preguntas sobre esta política de privacidad pueden dirigirse a comercial@trackflow.com.",
    },
  },
};
