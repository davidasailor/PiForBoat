-- MySQL dump 10.13  Distrib 8.0.28, for Linux (x86_64)
--
-- Host: localhost    Database: BoatServer
-- ------------------------------------------------------
-- Server version	5.5.5-10.5.16-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `status`
--

DROP TABLE IF EXISTS `status`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `status` (
  `datetime` datetime NOT NULL,
  `voltage` double DEFAULT NULL,
  `minv` double DEFAULT NULL,
  `maxv` double DEFAULT NULL,
  `minh` double DEFAULT NULL,
  `maxh` double DEFAULT NULL,
  `heel` double DEFAULT NULL,
  `latgps` float(10,6) DEFAULT NULL,
  `longps` float(10,6) DEFAULT NULL,
  `latgprs` float(10,6) DEFAULT NULL,
  `longprs` float(10,6) DEFAULT NULL,
  `temperature` double DEFAULT NULL,
  `lastnav` datetime DEFAULT NULL,
  `lastbilge` datetime DEFAULT NULL,
  `engv` double DEFAULT NULL,
  `minengv` double DEFAULT NULL,
  `maxengv` double DEFAULT NULL,
  `auxv` double DEFAULT NULL,
  `minauxv` double DEFAULT NULL,
  `maxauxv` double DEFAULT NULL,
  `amps` double DEFAULT NULL,
  `minamps` double DEFAULT NULL,
  `maxamps` double DEFAULT NULL,
  `fuel` double DEFAULT NULL,
  `water1` double DEFAULT NULL,
  `water2` double DEFAULT NULL,
  `ah` double DEFAULT NULL,
  `engTemp` double DEFAULT NULL,
  `minEngTemp` double DEFAULT NULL,
  `maxEngTemp` double DEFAULT NULL,
  `exhaustTemp` double DEFAULT NULL,
  `minExhaustTemp` double DEFAULT NULL,
  `maxExhaustTemp` double DEFAULT NULL,
  `RPMs` double DEFAULT NULL,
  `maxRPMs` double DEFAULT NULL,
  `minRPMs` double DEFAULT NULL,
  `minGasLevel` double DEFAULT NULL,
  `gasLevel` double DEFAULT NULL,
  `maxGasLevel` double DEFAULT NULL,
  `minNetCurrent` double DEFAULT NULL,
  `netCurrent` double DEFAULT NULL,
  `maxNetCurrent` double DEFAULT NULL,
  `soc` double DEFAULT NULL,
  `bilgeCount` double DEFAULT NULL,
  `minHouseBattTemp` double DEFAULT NULL,
  `HouseBattTemp` double DEFAULT NULL,
  `maxHouseBattTemp` double DEFAULT NULL,
  PRIMARY KEY (`datetime`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2022-06-03 19:25:59
